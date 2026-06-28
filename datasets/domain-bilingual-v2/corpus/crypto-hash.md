---
title: Cryptographic hash functions
language: en
source: openai-codex-synthetic
---

# Cryptographic hash functions

## SHA-2 as a one-way digest primitive

A cryptographic hash function maps an input message of any practical length to a fixed-size value called a **hash**, **digest**, or **checksum**. The SHA-2 family, standardized by NIST in **FIPS 180-4**, includes **SHA-224**, **SHA-256**, **SHA-384**, **SHA-512**, **SHA-512/224**, and **SHA-512/256**. For example, SHA-256 produces a 256-bit digest, commonly written as 64 hexadecimal characters.

A hash function is not a cipher. It has no encryption key, no decryption operation, and no way to recover the original message from the digest. Its security goal is **one-wayness**: given a digest, it should be computationally infeasible to find any message that produced it. This property is also called **preimage resistance**.

Small input changes should produce unrelated-looking digest changes. The text `hello` and the text `Hello` produce completely different SHA-256 outputs, which makes hashes useful as compact fingerprints for data.

## Collision resistance and integrity

A second core property is **collision resistance**: it should be infeasible to find two different messages with the same digest. Since every fixed-size digest has a finite number of possible values, collisions must exist mathematically, but a secure hash makes finding one beyond practical reach. SHA-256 is designed for about 128 bits of collision security because of the birthday bound.

Hashes also aim for **second-preimage resistance**: given one specific message, it should be infeasible to construct a different message with the same digest. This matters for file replacement attacks, software archives, logs, and document records.

For integrity checking, a trusted publisher can provide a SHA-256 digest for a release file. A user downloads the file, computes the digest locally, and compares it with the trusted value. If the values differ, the data was corrupted or altered. If they match, the file is very likely identical to the one represented by the trusted digest.

## What hashes do not provide

Hash functions provide integrity evidence, not confidentiality. Publishing a SHA-256 digest does not hide the message, and hashing predictable data does not make it secret. A hash is also not proof of who created a message unless it is combined with a separate authentication mechanism. In applied cryptography, SHA-2 is therefore best understood as a one-way, collision-resistant fingerprint primitive for detecting change, not as encryption.
