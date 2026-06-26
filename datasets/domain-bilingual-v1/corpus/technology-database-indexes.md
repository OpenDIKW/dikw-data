---
title: Database Indexes and Query Speed
language: en
source: local-diverse-synthetic
---

# Database Indexes and Query Speed

## Read Performance

A database index stores selected column values in a structure such as a B-tree, allowing the database to find matching rows without scanning the whole table. Indexes are especially useful for filters, joins, and ordered results.

## Write Cost

Every insert, update, or delete must also update affected indexes. Too many indexes increase storage use and write latency. Good schema design chooses indexes that match important query patterns rather than indexing every column.

