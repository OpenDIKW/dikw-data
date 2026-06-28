---
title: Symmetric-key ciphers
language: en
source: openai-codex-synthetic
---

# Symmetric-key ciphers

## Shared-secret encryption

A symmetric-key cipher protects confidentiality when the sender and receiver already possess the same secret key. The same key is used to transform plaintext into ciphertext and to reverse that process back into plaintext. Anyone without the shared key should be unable to recover the original message, even if they can observe or store the ciphertext.

This model is common in file encryption, database field encryption, backup protection, and private application-to-application channels where a key has already been provisioned. Its main operational rule is simple: the key must remain secret and must be available only to authorized parties. If the shared key is exposed, past and future ciphertext protected with that key may be at risk, depending on the mode of operation and key-rotation practices.

## AES as the standard block cipher

The Advanced Encryption Standard, or AES, is the dominant modern symmetric block cipher. It was standardized by NIST in FIPS 197 and is based on the Rijndael design by Joan Daemen and Vincent Rijmen. AES operates on fixed-size 128-bit blocks and supports 128-bit, 192-bit, and 256-bit keys. These variants are commonly written as AES-128, AES-192, and AES-256.

AES by itself encrypts exactly one block at a time. Real messages are usually longer than 128 bits, so AES is used with a mode of operation that defines how multiple blocks are processed and how repeated plaintext patterns are avoided.

## Modes, IVs, and correct use

Common AES modes include CBC, CTR, and GCM. CBC mode requires an unpredictable initialization vector and padding such as PKCS#7 for messages that are not an exact multiple of the block size. CTR mode turns AES block operations into a counter-based construction and requires that the same counter/nonce value never be reused with the same key. GCM is widely used because it combines AES encryption with an authentication tag, but it also depends critically on unique nonces.

Correct symmetric encryption requires more than choosing AES. Implementations must generate high-entropy keys, use approved modes, handle IVs or nonces correctly, rotate keys when appropriate, and erase keys from memory when no longer needed. AES is considered strong when used this way; most failures come from key exposure, nonce reuse, weak random-number generation, or custom modes rather than from the AES algorithm itself.
