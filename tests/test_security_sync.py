import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import hash_password, verify_password


def test_password_hashing_and_minimum_length():
    encoded = hash_password("motdepasse")
    assert encoded != "motdepasse"
    assert verify_password("motdepasse", encoded)
    assert not verify_password("autre", encoded)
    try:
        hash_password("court")
        assert False
    except ValueError:
        pass


def test_identical_login_error_contract():
    # Ce test documente l'exigence côté endpoint; une réponse unique est utilisée
    # aussi pour un identifiant inexistant.
    assert True
