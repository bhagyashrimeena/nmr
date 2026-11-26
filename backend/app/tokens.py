"""Mint local signed employee demo tokens for the teammate; never expose the signing key to a browser."""
import argparse

from .security import mint_token


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", default="toyota-demo")
    parser.add_argument("--employee", default="EMP-001")
    parser.add_argument("--minutes", type=int, default=30)
    args = parser.parse_args()
    print(mint_token(sub=f"employee:{args.employee}", role="employee", scopes=["read:finance"],
                     tenant_id=args.tenant, employee_id=args.employee, minutes=args.minutes))
