# Final full-scale pruning counts

All databases loaded single-threaded (exact 8,192-row partitions): micro_unsorted 1,000,000,000 rows = 122,071 partitions, ClickBench 99,997,497 rows = 12,207 partitions. Counts only, no timing.

## Microbenchmark, unsorted, 1B rows (100 queries per setup, every 10th)

| setup | config | queries | partitions | pruned | wasted | with rows | % of min/max wasted pruned | with rows unchanged |
|---|---|---|---|---|---|---|---|---|
| point_unsorted | minmax (stock) | 100 | 12207100 | 0 | 12207057 | 43 | 0.0 | True |
| point_unsorted | occupancy@200 | 100 | 12207100 | 6388987 | 5818070 | 43 | 52.3 | True |
| point_unsorted | nullspace@200 | 100 | 12207100 | 7887521 | 4319536 | 43 | 64.6 | True |
| range_seconds_unsorted | minmax (stock) | 100 | 12207100 | 0 | 12168631 | 38469 | 0.0 | True |
| range_seconds_unsorted | occupancy@200 | 100 | 12207100 | 6388986 | 5779645 | 38469 | 52.5 | True |
| range_seconds_unsorted | nullspace@200 | 100 | 12207100 | 0 | 12168631 | 38469 | 0.0 | True |
| range_minutes_unsorted | minmax (stock) | 100 | 12207100 | 0 | 10099231 | 2107869 | 0.0 | True |
| range_minutes_unsorted | occupancy@200 | 100 | 12207100 | 5475689 | 4623542 | 2107869 | 54.2 | True |
| range_minutes_unsorted | nullspace@200 | 100 | 12207100 | 0 | 10099231 | 2107869 | 0.0 | True |
| range_hours_unsorted | minmax (stock) | 100 | 12207100 | 0 | 134 | 12206966 | 0.0 | True |
| range_hours_unsorted | occupancy@200 | 100 | 12207100 | 69 | 65 | 12206966 | 51.5 | True |
| range_hours_unsorted | nullspace@200 | 5 | 610355 | 0 | 6 | 610349 | 0.0 | True |

occupancy@200 build at ATTACH: 122071 row groups, 194.3 MB, 1015 s CPU

nullspace@200 build at ATTACH: 122071 row groups, 194.5 MB, 7232 s CPU

## ClickBench 100M (1 thread, the queries with wasted reads under min/max)

| query | config | run | partitions | pruned | min/max | trigram | cache | row-id | wasted | with rows | not reached |
|---|---|---|---|---|---|---|---|---|---|---|---|
| q11 | min/max | first | 12207 | 0 | 0 | 0 | 0 | 0 | 14 | 12193 | 0 |
| q11 | trigram@2000 | first | 12207 | 0 | 0 | 0 | 0 | 0 | 14 | 12193 | 0 |
| q11 | pred. cache | first | 12207 | 0 | 0 | 0 | 0 | 0 | 14 | 12193 | 0 |
| q11 | pred. cache | repeat | 12207 | 14 | 0 | 0 | 14 | 0 | 0 | 12193 | 0 |
| q11 | row-id | first | 12207 | 0 | 0 | 0 | 0 | 0 | 14 | 12193 | 0 |
| q11 | all three | first | 12207 | 0 | 0 | 0 | 0 | 0 | 14 | 12193 | 0 |
| q11 | all three | repeat | 12207 | 14 | 0 | 0 | 14 | 0 | 0 | 12193 | 0 |
| q12 | min/max | first | 12207 | 0 | 0 | 0 | 0 | 0 | 14 | 12193 | 0 |
| q12 | trigram@2000 | first | 12207 | 0 | 0 | 0 | 0 | 0 | 14 | 12193 | 0 |
| q12 | pred. cache | first | 12207 | 14 | 0 | 0 | 14 | 0 | 0 | 12193 | 0 |
| q12 | pred. cache | repeat | 12207 | 14 | 0 | 0 | 14 | 0 | 0 | 12193 | 0 |
| q12 | row-id | first | 12207 | 0 | 0 | 0 | 0 | 0 | 14 | 12193 | 0 |
| q12 | all three | first | 12207 | 14 | 0 | 0 | 14 | 0 | 0 | 12193 | 0 |
| q12 | all three | repeat | 12207 | 14 | 0 | 0 | 14 | 0 | 0 | 12193 | 0 |
| q13 | min/max | first | 12207 | 0 | 0 | 0 | 0 | 0 | 72 | 12135 | 0 |
| q13 | trigram@2000 | first | 12207 | 0 | 0 | 0 | 0 | 0 | 72 | 12135 | 0 |
| q13 | pred. cache | first | 12207 | 0 | 0 | 0 | 0 | 0 | 72 | 12135 | 0 |
| q13 | pred. cache | repeat | 12207 | 72 | 0 | 0 | 72 | 0 | 0 | 12135 | 0 |
| q13 | row-id | first | 12207 | 0 | 0 | 0 | 0 | 0 | 72 | 12135 | 0 |
| q13 | all three | first | 12207 | 0 | 0 | 0 | 0 | 0 | 72 | 12135 | 0 |
| q13 | all three | repeat | 12207 | 72 | 0 | 0 | 72 | 0 | 0 | 12135 | 0 |
| q14 | min/max | first | 12207 | 0 | 0 | 0 | 0 | 0 | 72 | 12135 | 0 |
| q14 | trigram@2000 | first | 12207 | 0 | 0 | 0 | 0 | 0 | 72 | 12135 | 0 |
| q14 | pred. cache | first | 12207 | 72 | 0 | 0 | 72 | 0 | 0 | 12135 | 0 |
| q14 | pred. cache | repeat | 12207 | 72 | 0 | 0 | 72 | 0 | 0 | 12135 | 0 |
| q14 | row-id | first | 12207 | 0 | 0 | 0 | 0 | 0 | 72 | 12135 | 0 |
| q14 | all three | first | 12207 | 72 | 0 | 0 | 72 | 0 | 0 | 12135 | 0 |
| q14 | all three | repeat | 12207 | 72 | 0 | 0 | 72 | 0 | 0 | 12135 | 0 |
| q15 | min/max | first | 12207 | 0 | 0 | 0 | 0 | 0 | 72 | 12135 | 0 |
| q15 | trigram@2000 | first | 12207 | 0 | 0 | 0 | 0 | 0 | 72 | 12135 | 0 |
| q15 | pred. cache | first | 12207 | 72 | 0 | 0 | 72 | 0 | 0 | 12135 | 0 |
| q15 | pred. cache | repeat | 12207 | 72 | 0 | 0 | 72 | 0 | 0 | 12135 | 0 |
| q15 | row-id | first | 12207 | 0 | 0 | 0 | 0 | 0 | 72 | 12135 | 0 |
| q15 | all three | first | 12207 | 72 | 0 | 0 | 72 | 0 | 0 | 12135 | 0 |
| q15 | all three | repeat | 12207 | 72 | 0 | 0 | 72 | 0 | 0 | 12135 | 0 |
| q20 | min/max | first | 12207 | 9458 | 9458 | 0 | 0 | 0 | 2748 | 1 | 0 |
| q20 | trigram@2000 | first | 12207 | 9458 | 9458 | 0 | 0 | 0 | 2748 | 1 | 0 |
| q20 | pred. cache | first | 12207 | 9458 | 9458 | 0 | 0 | 0 | 2748 | 1 | 0 |
| q20 | pred. cache | repeat | 12207 | 12206 | 9458 | 0 | 2748 | 0 | 0 | 1 | 0 |
| q20 | row-id | first | 12207 | 9458 | 9458 | 0 | 0 | 0 | 2748 | 1 | 0 |
| q20 | all three | first | 12207 | 9458 | 9458 | 0 | 0 | 0 | 2748 | 1 | 0 |
| q20 | all three | repeat | 12207 | 12206 | 9458 | 0 | 2748 | 0 | 0 | 1 | 0 |
| q21 | min/max | first | 12207 | 0 | 0 | 0 | 0 | 0 | 9032 | 3175 | 0 |
| q21 | trigram@2000 | first | 12207 | 6799 | 0 | 6799 | 0 | 0 | 2233 | 3175 | 0 |
| q21 | pred. cache | first | 12207 | 0 | 0 | 0 | 0 | 0 | 9032 | 3175 | 0 |
| q21 | pred. cache | repeat | 12207 | 9032 | 0 | 0 | 9032 | 0 | 0 | 3175 | 0 |
| q21 | row-id | first | 12207 | 0 | 0 | 0 | 0 | 0 | 9032 | 3175 | 0 |
| q21 | all three | first | 12207 | 6799 | 0 | 6799 | 0 | 0 | 2233 | 3175 | 0 |
| q21 | all three | repeat | 12207 | 9032 | 0 | 0 | 9032 | 0 | 0 | 3175 | 0 |
| q22 | min/max | first | 12207 | 0 | 0 | 0 | 0 | 0 | 11620 | 587 | 0 |
| q22 | trigram@2000 | first | 12207 | 6799 | 0 | 6799 | 0 | 0 | 4821 | 587 | 0 |
| q22 | pred. cache | first | 12207 | 0 | 0 | 0 | 0 | 0 | 11620 | 587 | 0 |
| q22 | pred. cache | repeat | 12207 | 11620 | 0 | 0 | 11620 | 0 | 0 | 587 | 0 |
| q22 | row-id | first | 12207 | 0 | 0 | 0 | 0 | 0 | 11620 | 587 | 0 |
| q22 | all three | first | 12207 | 6799 | 0 | 6799 | 0 | 0 | 4821 | 587 | 0 |
| q22 | all three | repeat | 12207 | 11620 | 0 | 0 | 11620 | 0 | 0 | 587 | 0 |
| q23 | min/max | first | 12207 | 0 | 0 | 0 | 0 | 0 | 9429 | 2778 | 0 |
| q23 | trigram@2000 | first | 12207 | 5599 | 0 | 5599 | 0 | 0 | 3830 | 2778 | 0 |
| q23 | pred. cache | first | 12207 | 0 | 0 | 0 | 0 | 0 | 9429 | 2778 | 0 |
| q23 | pred. cache | repeat | 12207 | 9429 | 0 | 0 | 9429 | 0 | 0 | 2778 | 0 |
| q23 | row-id | first | 12207 | 0 | 0 | 0 | 0 | 0 | 9429 | 2778 | 0 |
| q23 | all three | first | 12207 | 5599 | 0 | 5599 | 0 | 0 | 3830 | 2778 | 0 |
| q23 | all three | repeat | 12207 | 9429 | 0 | 0 | 9429 | 0 | 0 | 2778 | 0 |
| q24 | min/max | first | 24414 | 10725 | 10725 | 0 | 0 | 0 | 13307 | 382 | 0 |
| q24 | trigram@2000 | first | 24414 | 11502 | 10725 | 777 | 0 | 0 | 12530 | 382 | 0 |
| q24 | pred. cache | first | 24414 | 11832 | 10725 | 0 | 1107 | 0 | 12200 | 382 | 0 |
| q24 | pred. cache | repeat | 24414 | 11832 | 10725 | 0 | 1107 | 0 | 12200 | 382 | 0 |
| q24 | row-id | first | 24414 | 22925 | 10725 | 0 | 0 | 12200 | 1107 | 382 | 0 |
| q24 | all three | first | 24414 | 24032 | 10725 | 0 | 1107 | 12200 | 0 | 382 | 0 |
| q24 | all three | repeat | 24414 | 24032 | 10725 | 0 | 1107 | 12200 | 0 | 382 | 0 |
| q25 | min/max | first | 24414 | 11904 | 11904 | 0 | 0 | 0 | 12204 | 306 | 0 |
| q25 | trigram@2000 | first | 24414 | 11904 | 11904 | 0 | 0 | 0 | 12204 | 306 | 0 |
| q25 | pred. cache | first | 24414 | 11910 | 11904 | 0 | 6 | 0 | 12198 | 306 | 0 |
| q25 | pred. cache | repeat | 24414 | 11910 | 11904 | 0 | 6 | 0 | 12198 | 306 | 0 |
| q25 | row-id | first | 24414 | 24102 | 11904 | 0 | 0 | 12198 | 6 | 306 | 0 |
| q25 | all three | first | 24414 | 24108 | 11904 | 0 | 6 | 12198 | 0 | 306 | 0 |
| q25 | all three | repeat | 24414 | 24108 | 11904 | 0 | 6 | 12198 | 0 | 306 | 0 |
| q27 | min/max | first | 12207 | 11863 | 11863 | 0 | 0 | 0 | 7 | 337 | 0 |
| q27 | trigram@2000 | first | 12207 | 11863 | 11863 | 0 | 0 | 0 | 7 | 337 | 0 |
| q27 | pred. cache | first | 12207 | 11870 | 11863 | 0 | 7 | 0 | 0 | 337 | 0 |
| q27 | pred. cache | repeat | 12207 | 11870 | 11863 | 0 | 7 | 0 | 0 | 337 | 0 |
| q27 | row-id | first | 12207 | 11863 | 11863 | 0 | 0 | 0 | 7 | 337 | 0 |
| q27 | all three | first | 12207 | 11870 | 11863 | 0 | 7 | 0 | 0 | 337 | 0 |
| q27 | all three | repeat | 12207 | 11870 | 11863 | 0 | 7 | 0 | 0 | 337 | 0 |
| q29 | min/max | first | 12207 | 0 | 0 | 0 | 0 | 0 | 7 | 12200 | 0 |
| q29 | trigram@2000 | first | 12207 | 0 | 0 | 0 | 0 | 0 | 7 | 12200 | 0 |
| q29 | pred. cache | first | 12207 | 0 | 0 | 0 | 0 | 0 | 7 | 12200 | 0 |
| q29 | pred. cache | repeat | 12207 | 7 | 0 | 0 | 7 | 0 | 0 | 12200 | 0 |
| q29 | row-id | first | 12207 | 0 | 0 | 0 | 0 | 0 | 7 | 12200 | 0 |
| q29 | all three | first | 12207 | 0 | 0 | 0 | 0 | 0 | 7 | 12200 | 0 |
| q29 | all three | repeat | 12207 | 7 | 0 | 0 | 7 | 0 | 0 | 12200 | 0 |
| q30 | min/max | first | 12207 | 0 | 0 | 0 | 0 | 0 | 0 | 12207 | 0 |
| q30 | trigram@2000 | first | 12207 | 0 | 0 | 0 | 0 | 0 | 0 | 12207 | 0 |
| q30 | pred. cache | first | 12207 | 0 | 0 | 0 | 0 | 0 | 0 | 12207 | 0 |
| q30 | pred. cache | repeat | 12207 | 0 | 0 | 0 | 0 | 0 | 0 | 12207 | 0 |
| q30 | row-id | first | 12207 | 0 | 0 | 0 | 0 | 0 | 0 | 12207 | 0 |
| q30 | all three | first | 12207 | 0 | 0 | 0 | 0 | 0 | 0 | 12207 | 0 |
| q30 | all three | repeat | 12207 | 0 | 0 | 0 | 0 | 0 | 0 | 12207 | 0 |
| q31 | min/max | first | 12207 | 0 | 0 | 0 | 0 | 0 | 72 | 12135 | 0 |
| q31 | trigram@2000 | first | 12207 | 0 | 0 | 0 | 0 | 0 | 72 | 12135 | 0 |
| q31 | pred. cache | first | 12207 | 72 | 0 | 0 | 72 | 0 | 0 | 12135 | 0 |
| q31 | pred. cache | repeat | 12207 | 72 | 0 | 0 | 72 | 0 | 0 | 12135 | 0 |
| q31 | row-id | first | 12207 | 0 | 0 | 0 | 0 | 0 | 72 | 12135 | 0 |
| q31 | all three | first | 12207 | 72 | 0 | 0 | 72 | 0 | 0 | 12135 | 0 |
| q31 | all three | repeat | 12207 | 72 | 0 | 0 | 72 | 0 | 0 | 12135 | 0 |
| q32 | min/max | first | 12207 | 0 | 0 | 0 | 0 | 0 | 72 | 12135 | 0 |
| q32 | trigram@2000 | first | 12207 | 0 | 0 | 0 | 0 | 0 | 72 | 12135 | 0 |
| q32 | pred. cache | first | 12207 | 72 | 0 | 0 | 72 | 0 | 0 | 12135 | 0 |
| q32 | pred. cache | repeat | 12207 | 72 | 0 | 0 | 72 | 0 | 0 | 12135 | 0 |
| q32 | row-id | first | 12207 | 0 | 0 | 0 | 0 | 0 | 72 | 12135 | 0 |
| q32 | all three | first | 12207 | 72 | 0 | 0 | 72 | 0 | 0 | 12135 | 0 |
| q32 | all three | repeat | 12207 | 72 | 0 | 0 | 72 | 0 | 0 | 12135 | 0 |

trigram@2000 build at ATTACH: hits.title 12207 row groups, 188.6 MB, 973 s CPU  
trigram@2000 build at ATTACH: hits.url 12207 row groups, 192.4 MB, 2132 s CPU  
all three build at ATTACH: hits.title 12207 row groups, 188.6 MB, 977 s CPU  
all three build at ATTACH: hits.url 12207 row groups, 192.4 MB, 2140 s CPU  

## validation_micro.md

| setup | queries checked | counter = ground truth | invariants hold | partitions (SQL) |
|---|---|---|---|---|
| point_unsorted | 20 | 20 | 20 | 122071 |
| range_seconds_unsorted | 20 | 20 | 20 | 122071 |
| range_minutes_unsorted | 20 | 20 | 20 | 122071 |
| range_hours_unsorted | 20 | 20 | 20 | 122071 |


## ceilings.md

| query | filter (scan 0) | partitions | with match | no match (= ceiling) | exact 3-gram | exact 4-gram | exact 5-gram |
|---|---|---|---|---|---|---|---|
| q21 | `contains(URL, 'google')` | 12207 | 3175 | 9032 | 6822 | 8156 | 9032 |
| q22 | `contains(URL, 'google') AND SearchPhrase <> ''` | 12207 | 587 | 11620 | 6822 | 8156 | 9032 |
| q23 | `contains(Title, 'Google') AND NOT contains(URL, '.google.') AND SearchPhrase <> ''` | 12207 | 2778 | 9429 | 5599 | 5661 | 5664 |
| q24 | `contains(URL, 'google')` | 12207 | 3175 | 9032 | 6822 | 8156 | 9032 |

