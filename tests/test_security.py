from app.core.security import hash_password, verify_password


class TestSecurity:
    def test_hash_and_verify(self):
        password = "secure123"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed)
        assert not verify_password("wrong", hashed)

    def test_different_hashes_for_same_password(self):
        password = "abc123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)
