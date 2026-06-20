# Choice News Topics

This file family stores user-curated Choice `cnq(..., "sectornews", ..., cnqCallback)` topic subscriptions as repo assets.

## Files

- Raw command: `config/choice_news_cnq_2026-04-09.txt`
- Structured asset: `config/choice_news_topics.json`

## Purpose

The raw file preserves the exact operator-supplied Choice command.

The JSON file makes the same subscription reusable by code or future loaders:

- `catalog_version`
- `vendor_name`
- `subscription_mode`
- `content_type`
- `callback_name`
- `groups[]`
- `topics[]`

## Current scope

This asset now has a smoke-level runtime loader.

Current runtime support:

- load structured topics from `config/choice_news_topics.json`
- call `ChoiceClient.cnq(...)`
- chunk topic codes into vendor-safe slices
- immediately `cnqcancel(...)` after each successful subscribe call

This is still not a full persistence/query pipeline for news content.

## Live constraint

Live smoke on 2026-04-10 confirmed that the current account can subscribe to `sectornews` successfully when the request contains 4 topic codes, and fails when a single request attempts all 21 topic codes at once.

Implication:

- the asset is still useful as the canonical topic registry
- runtime execution must not assume the whole group can be subscribed in one `cnq` call
- the current smoke task applies explicit chunking and immediate cancel
- any future long-lived subscriber must keep a deliberate selection/chunking policy instead of blindly sending the full list

## Notes

- `topic_code` values remain vendor-native.
- `topic_name` values are the user-provided labels from the original command.
- Future runtime code should prefer the structured JSON asset and keep the raw command file as a fallback/reference.
