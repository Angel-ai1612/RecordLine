# DocTrace Synthetic Evaluation

> These results come from a small, generated synthetic dataset. They are regression evidence only and are not general accuracy claims.

## Method and scoring policy

- Ground truth: `backend/tests/data/ground_truth.json`, generated independently from scenario definitions.
- `keyword_entity`: 70% extracted-entity overlap and 30% TF-IDF lexical similarity.
- `semantic_tfidf`: TF-IDF unigram/bigram cosine similarity only.
- `hybrid`: configured entity, TF-IDF, explicit-reference and temporal weights.
- Relationship threshold: `0.42`. Held-out labels were never used for tuning: `true`.
- OCR mode during this run: `rapidocr`.
- Zero-denominator policy: If both expected and predicted sets are empty, precision/recall are 1.0; otherwise a zero denominator is 0.0.
- Relationship metrics are typed and calculated over annotated positives plus explicit must-not-link negatives. Unlabelled predicted pairs remain unknown, so relationship precision is labelled precision, not exhaustive-corpus precision. Conflict metrics use project, canonical field and normalized value set. Evidence accuracy requires expected relationship type, reason-relevant passages from both documents, and independently labelled conflict facts. Timeline accuracy requires an expected event with exact eventDate and fileDate plus label-relevant source text.

## Dev results

| Method | Relationship labelled P / R / F1 | Must-not violations | Conflict P / R | Evidence | Timeline | OCR amount | Fact status/value | Seconds |
| --- | --- | ---: | --- | --- | --- | --- | --- | ---: |
| keyword_entity | 100.0% / 100.0% / 100.0% | 0 | 100.0% / 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 6.021 |
| semantic_tfidf | 0.0% / 0.0% / 0.0% | 0 | 0.0% / 0.0% | N/A | 100.0% | 100.0% | 100.0% | 5.913 |
| hybrid | 100.0% / 100.0% / 100.0% | 0 | 100.0% / 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 6.028 |

### Per-format extraction and fact results

| Format | Files | Files with passages | Expected facts | Correct facts | Fact accuracy | Extraction seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| docx | 3 | 3 | 4 | 4 | 100.0% | 0.069 |
| jpg | 1 | 1 | 1 | 1 | 100.0% | 2.117 |
| pdf | 6 | 6 | 8 | 8 | 100.0% | 0.020 |
| pdf-image | 1 | 1 | 1 | 1 | 100.0% | 2.011 |
| png | 1 | 1 | 1 | 1 | 100.0% | 1.600 |
| xlsx | 2 | 2 | 3 | 3 | 100.0% | 0.015 |

## Heldout results

| Method | Relationship labelled P / R / F1 | Must-not violations | Conflict P / R | Evidence | Timeline | OCR amount | Fact status/value | Seconds |
| --- | --- | ---: | --- | --- | --- | --- | --- | ---: |
| keyword_entity | 100.0% / 100.0% / 100.0% | 0 | 100.0% / 100.0% | 100.0% | 100.0% | N/A | 100.0% | 0.085 |
| semantic_tfidf | 0.0% / 0.0% / 0.0% | 0 | 100.0% / 100.0% | N/A | 100.0% | N/A | 100.0% | 0.066 |
| hybrid | 100.0% / 100.0% / 100.0% | 0 | 100.0% / 100.0% | 100.0% | 100.0% | N/A | 100.0% | 0.081 |

### Per-format extraction and fact results

| Format | Files | Files with passages | Expected facts | Correct facts | Fact accuracy | Extraction seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| docx | 2 | 2 | 2 | 2 | 100.0% | 0.013 |
| pdf | 4 | 4 | 3 | 3 | 100.0% | 0.007 |
| xlsx | 2 | 2 | 1 | 1 | 100.0% | 0.007 |

## Limitations observed in this run

- RapidOCR was active for this run; OCR scores cover only the generated noisy receipt variants.
- Processing time is local wall-clock time on one machine and is not a capacity benchmark.
- The synthetic corpus is intentionally tiny. A score of 100% on any metric is not evidence of real-world accuracy.
