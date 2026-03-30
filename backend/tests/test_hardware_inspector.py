from app.core.p2p_cli import HardwareInspector


def test_hardware_inspector_uses_weighted_formula(monkeypatch):
    inspector = HardwareInspector()
    monkeypatch.setattr(inspector, "_ram_mb", lambda: 16384)
    monkeypatch.setattr(
        inspector,
        "_detect_windows",
        lambda: {
            "cpu_model": "Intel Core i9-14900K",
            "cpu_physical_cores": 24,
            "cpu_max_clock_mhz": 5600,
            "gpu_model": "RTX 4090",
            "gpu_vram_mb": 24576,
            "gpu_driver": "551.23",
        },
    )
    monkeypatch.setattr(inspector, "os_name", "Windows")

    specs = inspector.get_specs()
    expected = round((0.35 * specs["cpu_score"]) + (0.55 * specs["gpu_score"]) + (0.10 * specs["ram_score"]), 2)
    assert specs["total_score"] == expected
    assert specs["gpu_vram_mb"] == 24576
