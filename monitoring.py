"""
Resource monitoring utilities for tracking CPU and GPU utilization during training.
"""

import os
import subprocess
import threading
import time
from typing import Optional

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import pynvml
    HAS_PYNVML = True
except ImportError:
    HAS_PYNVML = False

import torch


class ResourceMonitor:
    """Monitor CPU and GPU utilization during training."""
    
    def __init__(self, interval: float = 0.5):
        self.interval = interval
        self.cpu_usage = []
        self.gpu_usage = []
        self.gpu_memory = []
        self.timestamps = []
        self.monitoring = False
        self.start_time = None
        
        # Initialize GPU monitoring if available
        self.gpu_available = False
        self.gpu_monitoring_method = "none"
        
        # Try multiple methods for GPU monitoring
        if HAS_PYNVML:
            try:
                pynvml.nvmlInit()
                device_count = pynvml.nvmlDeviceGetCount()
                if device_count > 0:
                    self.gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    # Test if we can actually get GPU info
                    test_util = pynvml.nvmlDeviceGetUtilizationRates(self.gpu_handle)
                    self.gpu_available = True
                    self.gpu_monitoring_method = "pynvml"
                    print(f"✅ GPU monitoring via pynvml: {device_count} device(s) detected")
                else:
                    print("❌ pynvml initialized but no GPU devices found")
            except Exception as e:
                print(f"❌ pynvml GPU monitoring failed: {e}")
                # Try alternative methods for local development
                self._try_alternative_gpu_monitoring()
        else:
            print("❌ pynvml not available, trying alternative methods")
            self._try_alternative_gpu_monitoring()
    
    def _try_alternative_gpu_monitoring(self):
        """Try alternative GPU monitoring methods for local development."""
        # Method 1: Try using nvidia-smi command
        try:
            result = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total', 
                                   '--format=csv,noheader,nounits'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self.gpu_available = True
                self.gpu_monitoring_method = "nvidia-smi"
                print("✅ GPU monitoring via nvidia-smi command")
                return
        except Exception as e:
            print(f"❌ nvidia-smi monitoring failed: {e}")
        
        # Method 2: Check if we're in a CUDA environment
        if torch.cuda.is_available():
            try:
                torch.cuda.current_device()
                torch.cuda.get_device_properties(0)
                self.gpu_available = True
                self.gpu_monitoring_method = "torch-cuda"
                print("✅ GPU monitoring via PyTorch CUDA (limited metrics)")
                return
            except Exception as e:
                print(f"❌ PyTorch CUDA monitoring failed: {e}")
        
        print("❌ No working GPU monitoring method found")
    
    def _get_gpu_stats_nvidia_smi(self):
        """Get GPU stats using nvidia-smi command."""
        try:
            result = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total', 
                                   '--format=csv,noheader,nounits'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if lines:
                    parts = lines[0].split(', ')
                    if len(parts) >= 3:
                        gpu_util = float(parts[0])
                        mem_used = float(parts[1])
                        mem_total = float(parts[2])
                        mem_percent = (mem_used / mem_total) * 100
                        return gpu_util, mem_percent
        except Exception as e:
            print(f"nvidia-smi error: {e}")
        return 0, 0
    
    def _get_gpu_stats_torch(self):
        """Get basic GPU stats using PyTorch (limited information)."""
        try:
            if torch.cuda.is_available():
                # Get memory usage
                mem_used = torch.cuda.memory_allocated(0)
                mem_total = torch.cuda.max_memory_allocated(0)
                if mem_total > 0:
                    mem_percent = (mem_used / mem_total) * 100
                else:
                    mem_percent = 0
                
                # We can't get actual GPU utilization from PyTorch easily,
                # so we'll estimate based on whether GPU operations are happening
                # This is a rough approximation
                gpu_util = min(50, mem_percent)  # Very rough estimate
                return gpu_util, mem_percent
        except Exception as e:
            print(f"PyTorch GPU monitoring error: {e}")
        return 0, 0
    
    def start_monitoring(self):
        """Start monitoring in a separate thread."""
        self.monitoring = True
        self.start_time = time.time()
        thread = threading.Thread(target=self._monitor_loop)
        thread.daemon = True
        thread.start()
        return thread
    
    def stop_monitoring(self):
        """Stop monitoring."""
        self.monitoring = False
    
    def _monitor_loop(self):
        """Main monitoring loop that runs in a separate thread."""
        while self.monitoring:
            try:
                # Get timestamp relative to start
                current_time = time.time() - self.start_time
                self.timestamps.append(current_time)
                
                # Monitor CPU usage
                if HAS_PSUTIL:
                    cpu_percent = psutil.cpu_percent(interval=None)
                    self.cpu_usage.append(cpu_percent)
                else:
                    self.cpu_usage.append(0)
                
                # Monitor GPU usage
                if self.gpu_available:
                    try:
                        # Use the appropriate monitoring method
                        if self.gpu_monitoring_method == "pynvml":
                            # Get GPU utilization via pynvml
                            gpu_util = pynvml.nvmlDeviceGetUtilizationRates(self.gpu_handle)
                            self.gpu_usage.append(gpu_util.gpu)
                            
                            # Get GPU memory usage
                            gpu_mem = pynvml.nvmlDeviceGetMemoryInfo(self.gpu_handle)
                            memory_percent = (gpu_mem.used / gpu_mem.total) * 100
                            self.gpu_memory.append(memory_percent)
                            
                        elif self.gpu_monitoring_method == "nvidia-smi":
                            gpu_util, mem_percent = self._get_gpu_stats_nvidia_smi()
                            self.gpu_usage.append(gpu_util)
                            self.gpu_memory.append(mem_percent)
                            
                        elif self.gpu_monitoring_method == "torch-cuda":
                            gpu_util, mem_percent = self._get_gpu_stats_torch()
                            self.gpu_usage.append(gpu_util)
                            self.gpu_memory.append(mem_percent)
                            
                        else:
                            self.gpu_usage.append(0)
                            self.gpu_memory.append(0)
                            
                    except Exception as e:
                        print(f"Error getting GPU stats: {e}")
                        self.gpu_usage.append(0)
                        self.gpu_memory.append(0)
                else:
                    self.gpu_usage.append(0)
                    self.gpu_memory.append(0)
                
                time.sleep(self.interval)
                
            except Exception as e:
                print(f"Monitoring error: {e}")
                time.sleep(self.interval)
    
    def generate_html_visualization(self) -> str:
        """Generate HTML visualization with Chart.js."""
        
        # Get job ID from environment or generate one
        job_id = os.environ.get('JOB_ID', 'unknown')
        
        # Prepare data for Chart.js
        timestamps_str = [f"{t:.1f}" for t in self.timestamps]
        cpu_data = self.cpu_usage
        gpu_data = self.gpu_usage
        gpu_mem_data = self.gpu_memory
        
        # Calculate statistics
        avg_cpu = sum(cpu_data) / len(cpu_data) if cpu_data else 0
        max_cpu = max(cpu_data) if cpu_data else 0
        avg_gpu = sum(gpu_data) / len(gpu_data) if gpu_data else 0
        max_gpu = max(gpu_data) if gpu_data else 0
        avg_gpu_mem = sum(gpu_mem_data) / len(gpu_mem_data) if gpu_mem_data else 0
        max_gpu_mem = max(gpu_mem_data) if gpu_mem_data else 0
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>GPU Training Monitor (Job: {job_id})</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                    margin: 0;
                    padding: 20px;
                    color: #333;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 15px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                    padding: 30px;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                    border-bottom: 2px solid #eee;
                    padding-bottom: 20px;
                }}
                .header h1 {{
                    color: #2c3e50;
                    margin: 0;
                    font-size: 2.5em;
                    font-weight: 300;
                }}
                .job-info {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 15px;
                    border-radius: 10px;
                    margin-bottom: 20px;
                    text-align: center;
                }}
                .stats-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }}
                .stat-card {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 20px;
                    border-radius: 10px;
                    text-align: center;
                    box-shadow: 0 5px 15px rgba(0,0,0,0.1);
                }}
                .stat-card h3 {{
                    margin: 0 0 10px 0;
                    font-size: 1.2em;
                    opacity: 0.9;
                }}
                .stat-value {{
                    font-size: 2em;
                    font-weight: bold;
                    margin: 0;
                }}
                .chart-container {{
                    position: relative;
                    height: 400px;
                    margin: 20px 0;
                    background: #f8f9fa;
                    border-radius: 10px;
                    padding: 20px;
                    box-shadow: inset 0 2px 5px rgba(0,0,0,0.1);
                }}
                .chart-title {{
                    text-align: center;
                    margin-bottom: 20px;
                    font-size: 1.4em;
                    color: #2c3e50;
                    font-weight: 500;
                }}
                .gpu-card {{
                    background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
                }}
                .cpu-card {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }}
                .memory-card {{
                    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚀 Training Resource Monitor</h1>
                    <p>Real-time monitoring of CPU and GPU usage during model training</p>
                </div>
                
                <div class="job-info">
                    <h3>📊 Training Session</h3>
                    <p><strong>Job ID:</strong> {job_id}</p>
                </div>
                
                <div class="stats-grid">
                    <div class="stat-card cpu-card">
                        <h3>💻 Average CPU Usage</h3>
                        <p class="stat-value">{avg_cpu:.1f}%</p>
                    </div>
                    <div class="stat-card cpu-card">
                        <h3>🔥 Peak CPU Usage</h3>
                        <p class="stat-value">{max_cpu:.1f}%</p>
                    </div>
                    <div class="stat-card gpu-card">
                        <h3>🎮 Average GPU Usage</h3>
                        <p class="stat-value">{avg_gpu:.1f}%</p>
                    </div>
                    <div class="stat-card gpu-card">
                        <h3>⚡ Peak GPU Usage</h3>
                        <p class="stat-value">{max_gpu:.1f}%</p>
                    </div>
                    <div class="stat-card memory-card">
                        <h3>🧠 Average GPU Memory</h3>
                        <p class="stat-value">{avg_gpu_mem:.1f}%</p>
                    </div>
                    <div class="stat-card memory-card">
                        <h3>💾 Peak GPU Memory</h3>
                        <p class="stat-value">{max_gpu_mem:.1f}%</p>
                    </div>
                </div>
                
                <div class="chart-container">
                    <div class="chart-title">Resource Utilization Over Time</div>
                    <canvas id="utilizationChart"></canvas>
                </div>
            </div>
            
            <script>
                const ctx = document.getElementById('utilizationChart').getContext('2d');
                const chart = new Chart(ctx, {{
                    type: 'line',
                    data: {{
                        labels: {timestamps_str},
                        datasets: [{{
                            label: 'CPU Usage (%)',
                            data: {cpu_data},
                            borderColor: '#667eea',
                            backgroundColor: 'rgba(102, 126, 234, 0.1)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.4
                        }}, {{
                            label: 'GPU Usage (%)',
                            data: {gpu_data},
                            borderColor: '#11998e',
                            backgroundColor: 'rgba(17, 153, 142, 0.1)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.4
                        }}, {{
                            label: 'GPU Memory (%)',
                            data: {gpu_mem_data},
                            borderColor: '#f093fb',
                            backgroundColor: 'rgba(240, 147, 251, 0.1)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.4
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{
                                display: true,
                                position: 'top',
                                labels: {{
                                    usePointStyle: true,
                                    padding: 20,
                                    font: {{
                                        size: 12
                                    }}
                                }}
                            }},
                            tooltip: {{
                                mode: 'index',
                                intersect: false,
                                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                titleColor: 'white',
                                bodyColor: 'white',
                                borderColor: 'rgba(255, 255, 255, 0.2)',
                                borderWidth: 1,
                                cornerRadius: 8,
                                displayColors: true,
                                callbacks: {{
                                    title: function(context) {{
                                        return 'Time: ' + context[0].label + 's';
                                    }},
                                    label: function(context) {{
                                        const label = context.dataset.label;
                                        const value = context.parsed.y.toFixed(1);
                                        
                                        if (label === 'CPU Usage (%)') {{
                                            return [
                                                `CPU Usage: ${{value}}%`,
                                                '💻 How busy the CPU cores are',
                                                '📊 Higher = more processing work'
                                            ];
                                        }} else if (label === 'GPU Usage (%)') {{
                                            return [
                                                `GPU Usage: ${{value}}%`,
                                                '🎮 How busy the GPU compute cores are',
                                                '⚡ Higher = more parallel calculations'
                                            ];
                                        }} else if (label === 'GPU Memory (%)') {{
                                            return [
                                                `GPU Memory: ${{value}}%`,
                                                '🧠 How much GPU memory (VRAM) is used',
                                                '📦 Higher = more data loaded on GPU'
                                            ];
                                        }}
                                        return `${{label}}: ${{value}}%`;
                                    }},
                                    labelTextColor: function(context) {{
                                        return context.dataset.borderColor;
                                    }}
                                }}
                            }}
                        }},
                        scales: {{
                            x: {{
                                display: true,
                                title: {{
                                    display: true,
                                    text: 'Time (seconds)',
                                    font: {{
                                        size: 14,
                                        weight: 'bold'
                                    }}
                                }},
                                grid: {{
                                    color: 'rgba(0,0,0,0.1)'
                                }}
                            }},
                            y: {{
                                display: true,
                                title: {{
                                    display: true,
                                    text: 'Usage (%)',
                                    font: {{
                                        size: 14,
                                        weight: 'bold'
                                    }}
                                }},
                                min: 0,
                                max: 100,
                                grid: {{
                                    color: 'rgba(0,0,0,0.1)'
                                }}
                            }}
                        }},
                        elements: {{
                            point: {{
                                radius: 3,
                                hoverRadius: 6
                            }}
                        }},
                        interaction: {{
                            mode: 'index',
                            intersect: false
                        }}
                    }}
                }});
            </script>
        </body>
        </html>
        """
        
        return html_content 