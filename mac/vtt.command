#!/usr/bin/env bash
# Finder からダブルクリックで GUI を起動するためのランチャー。
# 初回は「右クリック → 開く」で許可が必要な場合があります。
cd "$(dirname "$0")/.." || exit 1
exec python3 mac/gui.py
