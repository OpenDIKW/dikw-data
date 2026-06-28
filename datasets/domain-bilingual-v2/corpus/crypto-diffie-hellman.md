---
title: Diffie–Hellman key exchange
language: en
source: openai-codex-synthetic
---

# Diffie–Hellman key exchange

Diffie–Hellman key exchange is the standard primitive for **agreeing a shared secret over a public channel with no prior shared key**. Published in 1976 by Whitfield Diffie and Martin Hellman, with related ideas from Ralph Merkle, it lets two parties derive the same secret value even though an eavesdropper can observe every message they send.

Diffie–Hellman is not message encryption and not an identity proof by itself. Its output is shared secret material that another protocol can turn into usable session keys.

## Core finite-field exchange

In classic finite-field Diffie–Hellman, both parties agree on public parameters: a large prime modulus `p` and a generator `g` of a suitable cyclic group. These values do not need to be secret.

1. Alice chooses a private random exponent `a` and sends `A = g^a mod p`.
2. Bob chooses a private random exponent `b` and sends `B = g^b mod p`.
3. Alice computes `s = B^a mod p`.
4. Bob computes `s = A^b mod p`.

Both results equal `g^(ab) mod p`, so Alice and Bob arrive at the same shared secret. An observer sees `p`, `g`, `A`, and `B`, but should not be able to recover `a`, `b`, or `g^(ab)` if the discrete logarithm problem is hard in the chosen group.

## Variants and named groups

Modern deployments often use elliptic-curve Diffie–Hellman, usually called ECDH. Instead of modular exponentiation in a finite field, ECDH uses scalar multiplication on an elliptic-curve group. Common named choices include Curve25519, used through X25519, and NIST P-256. Finite-field deployments may use standardized safe-prime groups such as those described in RFC 7919.

Ephemeral Diffie–Hellman uses fresh private values for each session. This prevents reuse of the same exchange secret and is the usual choice when building secure channels.

## Security properties and limits

Diffie–Hellman protects against a passive network observer, but unauthenticated Diffie–Hellman is vulnerable to an active man-in-the-middle who substitutes public values. Therefore real protocols pair it with a separate authentication mechanism and usually feed the raw shared value into a key-derivation step before use.

The distinctive purpose of Diffie–Hellman is key agreement: two parties with no prior shared key can create one across an untrusted public network.
