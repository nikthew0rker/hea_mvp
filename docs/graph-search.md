# graph-search.md

## 1. Purpose

Graph Search finds the most relevant published assessment graph for the current user conversation.

---

## 2. Input

- raw user message or analyzed intent
- graph registry metadata

---

## 3. Output

- ranked candidate list
- graph ids
- relevance scores
- short reasons

---

## 4. MVP search strategy

For MVP, graph search may use:
- tag overlap
- entry signal overlap
- search text overlap
- title/topic match

This is sufficient to demonstrate graph discovery without building a heavy ranking system.

