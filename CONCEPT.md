# SWAP — Signed Wallet-to-wallet Authenticated Payments

## Concept — v0.9

---

## 1. Goal

Offline peer-to-peer payments for 10M members of a microfinance in Cameroon. Each step of a payment gracefully falls back to QR scanning when connectivity is unavailable.

---

## 2. Cryptography

- **Ed25519** — 32-byte public keys, 64-byte signatures, fast on weak CPUs.
- Keys are **not static**. A member can rotate keys at any time. Key recovery = issue new key + new attestation.

---

## 3. Member Identity & Key Lookup

Members are identified by a **4-byte member ID** (phone number or sequential ID). Public keys are **not embedded in QR codes**. Instead:

- The app fetches a member's public key from the server by member ID.
- Lightweight, cacheable — no heavy database lookup required.
- Once fetched, cached locally and reused until key rotation.

---

## 4. Documents

### 4.1 Transfer (Payment)

Created and signed by the payer. The actual payment. The only document in the protocol.

```
Field          Size    Description
───────────────────────────────────────
sender_id       4      Payer's member ID (32-bit BE)
recipient_id    4      Payee's member ID (32-bit BE)
amount          3      Amount in FCFA (24-bit BE)
timestamp       4      Payment time (Unix timestamp, UTC)
sig_type        1      Signature algorithm identifier
key_hint        2      SHA-256(public_key)[0..1] — key disambiguation
sender_sig     64      Payer's signature over [0..17]
───────────────────────────────────────
Total:         82 bytes — QR V10 ECC-H (30%)
```

Self-contained: identifies both parties. When the payer is offline, this is shown on screen for the payee to scan. When online, pushed to the server.

### 4.2 Recipient QR — 107 bytes

Displayed by the payee (e.g., printed at a shop, on screen). Allows the payer to scan the payee's ID and name instead of typing it. Signed by MFI Root to prevent fake recipient IDs.

```
Field          Size    Description
───────────────────────────────────────
recipient_id    4      Payee's member ID (32-bit BE)
recipient_name 32      Payee's display name (UTF-8, padded)
timestamp       4      Issuance time (Unix timestamp, UTC)
sig_type        1      Signature algorithm identifier
key_hint        2      SHA-256(public_key)[0..1] — key disambiguation
root_sig       64      MFI Root signature over [0..42]
───────────────────────────────────────
Total:        107 bytes — QR V10 ECC-H (30%)
```

### 4.3 Identity QR — 111 bytes

Only needed when the payer is offline and the payee doesn't have the payer's public key cached. The payer shows this so the payee can verify the Transfer signature offline.

```
Field          Size    Description
───────────────────────────────────────
member_id       4      Member ID (32-bit BE)
public_key     33      Member's public key (Ed25519: 0x00 padded)
max_amount      3      Max spendable FCFA (24-bit BE)
valid_to        4      Expiry (Unix timestamp, UTC)
sig_type        1      Signature algorithm identifier
key_hint        2      SHA-256(public_key)[0..1] — key disambiguation
root_sig       64      MFI Root signature over [0..46]
───────────────────────────────────────
Total:        111 bytes — QR V10 ECC-H (30%)
```

---

## 5. Payment Flow

```
┌─────────────────────────────────────────────────────────┐
│                                                           │
│  Payer enters payee's ID and amount                      │
│  (or scans payee's Recipient QR).                        │
│                                                           │
│  IF payer is online:                                     │
│    • App fetches payee's public key (caches it)          │
│    • App signs Transfer                                  │
│    • App pushes Transfer to payee's Record Server        │
│    • Payee receives Transfer via push / next sync        │
│                                                           │
│  IF payer is offline (face-to-face):                     │
│    • App signs Transfer                                  │
│    • App displays Transfer QR for payee to scan          │
│    • Payee scans, verifies, confirms or rejects          │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

---

## 6. Connectivity Scenarios

| Payer | How it works | QR scans |
|---|---|---|
| Online | Payer signs and pushes Transfer to server. Payee receives on next sync. | **0** |
| Offline | Payer shows Transfer QR. Payee scans. | **1** |
| Offline + payee missing payer's key | Payer shows Identity QR, then Transfer QR. Payee scans both. | **2** |

---

## 7. QR Display & Scanning

| Document | Bytes | QR V10 ECC | Recovery | Headroom |
|---|---|---|---|---|
| Transfer | 82 | **H** | 30% | 30 bytes |
| Recipient | 107 | **H** | 30% | 5 bytes |
| Identity | 111 | **H** | 30% | 1 byte |

- All QRs are **57×57 modules** (QR Version 10).
- QR displayed **full-screen** on phone.
- All documents get maximum 30% error correction.

---

## 8. Verification Summary

### Transfer (by payee)

| Check | How |
|---|---|
| Payment is for me | `recipient_id == my_member_id` |
| Sender is authentic | `sender_sig` valid against payer's public key (cached or fetched) |
| Amount is correct | Displayed for payee confirmation |
| Timestamp fresh | Within acceptable window |

---

## 9. What Cannot Be Verified Offline

- **Payer's exact remaining balance.** The payer's app enforces balance checks locally, but a tampered app could lie.
- **Double spending.** The payer could sign transfers to multiple payees.

Both detected later by the Record Server. Deterrent: members are KYC'd. Fraud = wallet discard + account closure + legal action.

---

## 10. Key Properties

| Property | How |
|---|---|
| **Online-first** | Payer pushes Transfer to server; zero scans |
| **Offline-capable** | Payer shows Transfer QR; 1 scan |
| **82 bytes** | Transfer QR fits V10 (57×57) with 30% error correction |
| **1 document** | Transfer is the only payment document |
| **1-2 scans max** | Transfer only, or Identity + Transfer if key unknown |
| **Non-repudiable** | Payer signed the transfer |
| **Cacheable keys** | Fetched once by member ID, reused until rotation |
| **Simple** | Payer enters or scans payee ID, enters amount, confirms, done |

---

## 11. Example

> Alice buys bread from Bob for 500 FCFA.

**Alice online:**
Alice scans Bob's Recipient QR (or types his ID), enters 500 FCFA, confirms. Her app pushes the signed Transfer to the server. Bob sees: "500 FCFA from Alice — ACCEPTED."

**Alice offline (face-to-face):**
Alice scans Bob's Recipient QR (or types his ID), enters 500 FCFA, confirms. Her app shows the Transfer QR. Bob scans it: "500 FCFA from Alice — ACCEPTED."

**Alice offline, Bob doesn't know Alice's key:**
Alice first shows her Identity QR. Bob scans it — now has Alice's public key. Then Alice shows the Transfer QR. Bob scans it: "500 FCFA from Alice — ACCEPTED." Two scans, done.
