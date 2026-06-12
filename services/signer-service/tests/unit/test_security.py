import pytest

from hongguo_signer.security import filter_security_headers


@pytest.mark.parametrize(
    ("supplied", "canonical"),
    [
        ("x-argus", "X-Argus"),
        ("X-GORGON", "X-Gorgon"),
        ("x-LaDoN", "X-Ladon"),
        ("X-Khronos", "X-Khronos"),
        ("x-helios", "X-Helios"),
        ("X-MEDUSA", "X-Medusa"),
        ("x-ss-req-ticket", "X-SS-REQ-TICKET"),
    ],
)
def test_filter_security_headers_uses_canonical_case(
    supplied: str,
    canonical: str,
) -> None:
    assert filter_security_headers({supplied: "value"}) == {canonical: "value"}


def test_filter_security_headers_removes_session_data() -> None:
    result = filter_security_headers(
        {
            "X-Argus": "a",
            "x-gorgon": "g",
            "cookie": "session=secret",
            "authorization": "Bearer secret",
            "x-tt-token": "secret",
        }
    )

    assert result == {"X-Argus": "a", "X-Gorgon": "g"}


def test_filter_security_headers_ignores_empty_values_and_stringifies_values() -> None:
    result = filter_security_headers(
        {
            "X-Khronos": 123,
            "X-Helios": "",
            "X-Medusa": None,
        }
    )

    assert result == {"X-Khronos": "123"}
