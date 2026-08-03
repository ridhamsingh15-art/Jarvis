class HardwareMonitor:
    def get_stats(self) -> dict[str, float]:
        return {
            "cpu_percent": 15.5,
            "ram_percent": 45.0,
            "gpu_percent": 5.0,
            "battery_percent": 100.0
        }
