import tempfile
import json
from pathlib import Path
from backend.app.services.policy_normalization_v2 import PolicyNormalizerV2

def test_noise_removal():
    normalizer = PolicyNormalizerV2()
    assert normalizer.is_noise("CÔNG BÁO/Số 1643 + 1644/Ngày 03-12-2025", (0, 0, 0, 0), 842) == True
    assert normalizer.is_noise("CÔNG BÁO/Số 1/Ngày 11-11-2022", (0, 0, 0, 0), 842) == True
    assert normalizer.is_noise("1", (0, 0, 0, 50), 842) == True
    assert normalizer.is_noise("2", (0, 800, 0, 820), 842) == True
    assert normalizer.is_noise("1", (0, 400, 0, 420), 842) == False
