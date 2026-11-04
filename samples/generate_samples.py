#!/usr/bin/env python3
"""
Generate sample QR codes for SWAP protocol documents.
Each document is built as raw binary per the CONCEPT.md spec,
then encoded into a QR V10 ECC-H PNG image.
"""

import hashlib
import os
import struct
import time

import qrcode
from qrcode.constants import ERROR_CORRECT_H

SAMPLES_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Signature algorithm IDs ---
SIG_ED25519 = 0x01
SIG_SECP256R1 = 0x02
SIG_SECP256K1 = 0x03

# --- Fake keys (deterministic for reproducibility) ---
# Ed25519: 32-byte key, zero-padded to 33 in Identity QR
ALICE_PRIVKEY_SEED = b"alice-seed-for-sample-generation!"  # 32 bytes
ALICE_PUBKEY = hashlib.sha256(b"alice-pubkey").digest()  # fake 32-byte key

BOB_PRIVKEY_SEED = b"bob-seed-for-sample-generation!!"  # 32 bytes
BOB_PUBKEY = hashlib.sha256(b"bob-pubkey").digest()  # fake 32-byte key

# MFI Root key (fake)
ROOT_PUBKEY = hashlib.sha256(b"mfi-root-pubkey").digest()


def key_hint(pubkey: bytes) -> bytes:
    """First 2 bytes of SHA-256(public_key)."""
    return hashlib.sha256(pubkey).digest()[:2]


def fake_signature(data: bytes, label: str) -> bytes:
    """Generate a deterministic 64-byte fake signature for samples."""
    h = hashlib.sha256(data + label.encode()).digest()
    return h + h  # 64 bytes


def build_transfer(sender_id: int, recipient_id: int, amount: int,
                   ts: int, sig_type: int, sender_pubkey: bytes) -> bytes:
    """Build an 82-byte Transfer document."""
    header = struct.pack(">I", sender_id)           # 4 bytes
    header += struct.pack(">I", recipient_id)        # 4 bytes
    header += struct.pack(">I", amount)[1:]          # 3 bytes (24-bit BE)
    header += struct.pack(">I", ts)                  # 4 bytes
    header += struct.pack("B", sig_type)             # 1 byte
    header += key_hint(sender_pubkey)                # 2 bytes
    # Total header: 18 bytes, signature over [0..17]
    sig = fake_signature(header, "sender")
    doc = header + sig
    assert len(doc) == 82, f"Transfer is {len(doc)} bytes, expected 82"
    return doc


def build_recipient(recipient_id: int, name: str, ts: int,
                    sig_type: int, root_pubkey: bytes) -> bytes:
    """Build a 107-byte Recipient QR document."""
    header = struct.pack(">I", recipient_id)         # 4 bytes
    name_bytes = name.encode("utf-8")[:32].ljust(32, b'\x00')  # 32 bytes
    header += name_bytes
    header += struct.pack(">I", ts)                  # 4 bytes
    header += struct.pack("B", sig_type)             # 1 byte
    header += key_hint(root_pubkey)                  # 2 bytes
    # Total header: 43 bytes, signature over [0..42]
    sig = fake_signature(header, "root")
    doc = header + sig
    assert len(doc) == 107, f"Recipient is {len(doc)} bytes, expected 107"
    return doc


def build_identity(member_id: int, pubkey: bytes, max_amount: int,
                   valid_to: int, sig_type: int, root_pubkey: bytes) -> bytes:
    """Build a 111-byte Identity QR document."""
    header = struct.pack(">I", member_id)            # 4 bytes
    # Pad Ed25519 (32-byte) keys to 33 bytes with leading 0x00
    if len(pubkey) == 32:
        pubkey_padded = b'\x00' + pubkey
    else:
        pubkey_padded = pubkey[:33]
    header += pubkey_padded                          # 33 bytes
    header += struct.pack(">I", max_amount)[1:]      # 3 bytes (24-bit BE)
    header += struct.pack(">I", valid_to)            # 4 bytes
    header += struct.pack("B", sig_type)             # 1 byte
    header += key_hint(root_pubkey)                  # 2 bytes
    # Total header: 47 bytes, signature over [0..46]
    sig = fake_signature(header, "root")
    doc = header + sig
    assert len(doc) == 111, f"Identity is {len(doc)} bytes, expected 111"
    return doc


def make_qr_png(data: bytes, filename: str):
    """Generate a QR V10 ECC-H PNG from binary data."""
    qr = qrcode.QRCode(
        version=10,
        error_correction=ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=False)  # force V10
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(os.path.join(SAMPLES_DIR, filename))


def write_description(filename: str, doc_type: str, fields: dict, raw: bytes):
    """Write a human-readable text file describing the sample."""
    path = os.path.join(SAMPLES_DIR, filename)
    with open(path, "w") as f:
        f.write(f"SWAP Sample: {doc_type}\n")
        f.write(f"{'=' * 50}\n\n")
        for k, v in fields.items():
            f.write(f"{k:20s}: {v}\n")
        f.write(f"\n{'─' * 50}\n")
        f.write(f"Total bytes: {len(raw)}\n")
        f.write(f"Hex dump:\n{raw.hex()}\n")


def main():
    ts = int(time.time())
    valid_to = ts + 86400 * 30  # 30 days from now

    # --- Sample 1: Transfer (Alice pays Bob 500 FCFA) ---
    alice_id = 1001
    bob_id = 2002
    amount = 500

    transfer = build_transfer(alice_id, bob_id, amount, ts, SIG_ED25519, ALICE_PUBKEY)
    make_qr_png(transfer, "transfer_alice_to_bob.png")
    write_description("transfer_alice_to_bob.txt", "Transfer (Payment)", {
        "sender_id": f"{alice_id} (Alice)",
        "recipient_id": f"{bob_id} (Bob)",
        "amount": f"{amount} FCFA",
        "timestamp": f"{ts} (UTC)",
        "sig_type": f"0x{SIG_ED25519:02x} (Ed25519)",
        "key_hint": f"0x{key_hint(ALICE_PUBKEY).hex()}",
        "signature": "64-byte fake Ed25519 signature",
    }, transfer)

    # --- Sample 2: Transfer (Bob pays Alice 1200 FCFA, secp256r1) ---
    amount2 = 1200
    transfer2 = build_transfer(bob_id, alice_id, amount2, ts, SIG_SECP256R1, BOB_PUBKEY)
    make_qr_png(transfer2, "transfer_bob_to_alice.png")
    write_description("transfer_bob_to_alice.txt", "Transfer (Payment)", {
        "sender_id": f"{bob_id} (Bob)",
        "recipient_id": f"{alice_id} (Alice)",
        "amount": f"{amount2} FCFA",
        "timestamp": f"{ts} (UTC)",
        "sig_type": f"0x{SIG_SECP256R1:02x} (secp256r1)",
        "key_hint": f"0x{key_hint(BOB_PUBKEY).hex()}",
        "signature": "64-byte fake ECDSA signature",
    }, transfer2)

    # --- Sample 3: Recipient QR (Bob's shop) ---
    recipient = build_recipient(bob_id, "Bob's Boulangerie", ts, SIG_ED25519, ROOT_PUBKEY)
    make_qr_png(recipient, "recipient_bob.png")
    write_description("recipient_bob.txt", "Recipient QR", {
        "recipient_id": f"{bob_id} (Bob)",
        "recipient_name": "Bob's Boulangerie",
        "timestamp": f"{ts} (UTC)",
        "sig_type": f"0x{SIG_ED25519:02x} (Ed25519)",
        "key_hint": f"0x{key_hint(ROOT_PUBKEY).hex()} (MFI Root)",
        "signature": "64-byte fake Root signature",
    }, recipient)

    # --- Sample 4: Recipient QR (Alice) ---
    recipient2 = build_recipient(alice_id, "Alice Nguemo", ts, SIG_ED25519, ROOT_PUBKEY)
    make_qr_png(recipient2, "recipient_alice.png")
    write_description("recipient_alice.txt", "Recipient QR", {
        "recipient_id": f"{alice_id} (Alice)",
        "recipient_name": "Alice Nguemo",
        "timestamp": f"{ts} (UTC)",
        "sig_type": f"0x{SIG_ED25519:02x} (Ed25519)",
        "key_hint": f"0x{key_hint(ROOT_PUBKEY).hex()} (MFI Root)",
        "signature": "64-byte fake Root signature",
    }, recipient2)

    # --- Sample 5: Identity QR (Alice, Ed25519) ---
    identity = build_identity(alice_id, ALICE_PUBKEY, 50000, valid_to,
                              SIG_ED25519, ROOT_PUBKEY)
    make_qr_png(identity, "identity_alice.png")
    write_description("identity_alice.txt", "Identity QR", {
        "member_id": f"{alice_id} (Alice)",
        "public_key": f"Ed25519 (32 bytes, 0x00 padded to 33)",
        "max_amount": "50000 FCFA",
        "valid_to": f"{valid_to} (UTC)",
        "sig_type": f"0x{SIG_ED25519:02x} (Ed25519)",
        "key_hint": f"0x{key_hint(ROOT_PUBKEY).hex()} (MFI Root)",
        "signature": "64-byte fake Root signature",
    }, identity)

    # --- Sample 6: Identity QR (Bob, secp256k1) ---
    # Simulate a 33-byte compressed EC public key
    bob_ec_pubkey = b'\x02' + BOB_PUBKEY  # 0x02 prefix + 32 bytes = 33
    identity2 = build_identity(bob_id, bob_ec_pubkey, 100000, valid_to,
                               SIG_SECP256K1, ROOT_PUBKEY)
    make_qr_png(identity2, "identity_bob.png")
    write_description("identity_bob.txt", "Identity QR", {
        "member_id": f"{bob_id} (Bob)",
        "public_key": f"secp256k1 (33 bytes, compressed)",
        "max_amount": "100000 FCFA",
        "valid_to": f"{valid_to} (UTC)",
        "sig_type": f"0x{SIG_SECP256K1:02x} (secp256k1)",
        "key_hint": f"0x{key_hint(ROOT_PUBKEY).hex()} (MFI Root)",
        "signature": "64-byte fake Root signature",
    }, identity2)

    print("Generated 6 sample QR codes in", SAMPLES_DIR)
    for name in sorted(os.listdir(SAMPLES_DIR)):
        if name.endswith((".png", ".txt")):
            size = os.path.getsize(os.path.join(SAMPLES_DIR, name))
            print(f"  {name:40s} {size:>6d} bytes")


if __name__ == "__main__":
    main()
