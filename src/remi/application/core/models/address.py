"""Address — a physical location."""

from __future__ import annotations

from pydantic import BaseModel


class Address(BaseModel, frozen=True):
    street: str
    city: str
    state: str
    zip_code: str
    country: str = "US"

    def one_line(self) -> str:
        return f"{self.street}, {self.city}, {self.state} {self.zip_code}"
