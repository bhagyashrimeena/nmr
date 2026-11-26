"""Mint local signed employee tokens for the integration adapter."""
import argparse

from .security import mint_token


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", default="toyota-demo")
    parser.add_argument("--employee", default="EMP-001")
    parser.add_argument("--minutes", type=int, default=30)
    parser.add_argument("--draft", choices=["stock", "pension", "equity"],
                        help="Include a service-specific draft permission")
    args = parser.parse_args()
    scopes = ["read:finance"] + ([f"draft:{args.draft}"] if args.draft else [])
    print(mint_token(sub=f"employee:{args.employee}", role="employee", scopes=scopes,
                     tenant_id=args.tenant, employee_id=args.employee, minutes=args.minutes))
