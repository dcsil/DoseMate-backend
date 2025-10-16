from app.db.models import User


def test_user_repr_contains_email_and_provider():
    u = User()
    # SQLAlchemy model in tests may not accept constructor args; set attributes
    u.email = "tester@example.com"
    u.auth_provider = "google"
    r = repr(u)
    assert "email=tester@example.com" in r
    assert "provider=google" in r
