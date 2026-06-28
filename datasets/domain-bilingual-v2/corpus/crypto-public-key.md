---
title: Public-key cryptography
language: en
source: openai-codex-synthetic
---

# Public-key cryptography

Public-key cryptography uses an **asymmetric key pair**: a public key that may be distributed widely and a private key that must remain secret. Its central confidentiality pattern is simple: **encrypt with the public key, decrypt with the private key**. Anyone who knows the recipient’s public key can create ciphertext, but only the holder of the matching private key can recover the plaintext.

## Asymmetric key pairs and confidentiality

Unlike a shared-secret scheme, the two keys in an asymmetric pair are mathematically related but not interchangeable. The public key is placed in directories, certificates, configuration files, or messages; the private key is protected in a software keystore, hardware security module, smart card, or other restricted environment.

This model is useful when two parties do not already share a secret key. A sender can obtain Alice’s public key and encrypt a message for Alice without learning her private key. If Alice’s private key is lost, ciphertext encrypted to the corresponding public key is effectively unrecoverable. If the private key is copied or exposed, confidentiality for messages encrypted to that public key is no longer trustworthy.

## RSA encryption

**RSA**, named for Ron Rivest, Adi Shamir, and Leonard Adleman, is the classic public-key encryption algorithm. An RSA public key contains a modulus `n` and public exponent `e`; the private key contains secret values including a private exponent `d`. The modulus is derived from two large random primes. In simplified form, RSA encryption computes ciphertext from a message using the public key, and decryption reverses the operation using the private key.

Real RSA encryption must use a padding and encoding scheme. The modern standard is **RSAES-OAEP**, specified in **PKCS #1** and **RFC 8017**. “Textbook RSA” without padding is unsafe because it is deterministic and structurally malleable. Common contemporary RSA modulus sizes are **2048 bits** at a minimum, with **3072 bits** or larger chosen for longer security margins according to guidance such as NIST publications.

## Practical limits and responsibilities

RSA is not normally used to encrypt large files directly. It can encrypt only data smaller than the modulus after padding overhead, so systems often encrypt a compact secret value for the recipient and protect bulk data separately.

Public-key encryption provides confidentiality for the encrypted content, but it does not automatically prove who created the ciphertext or that external metadata was not changed. Correct public-key use therefore requires authentic public keys, secure random number generation, safe private-key storage, and well-reviewed implementations such as OpenSSL, BoringSSL, or platform cryptographic libraries.
