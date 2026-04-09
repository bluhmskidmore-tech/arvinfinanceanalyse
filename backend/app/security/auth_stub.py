from dataclasses import dataclass


@dataclass(frozen=True)
class AuthContext:
    user_id: str = "phase1-dev-user"
    role: str = "admin"
