| query | filter (scan 0) | partitions | with match | no match (= ceiling) | exact 3-gram | exact 4-gram | exact 5-gram |
|---|---|---|---|---|---|---|---|
| q21 | `contains(URL, 'google')` | 12207 | 3175 | 9032 | 6822 | 8156 | 9032 |
| q22 | `contains(URL, 'google') AND SearchPhrase <> ''` | 12207 | 587 | 11620 | 6822 | 8156 | 9032 |
| q23 | `contains(Title, 'Google') AND NOT contains(URL, '.google.') AND SearchPhrase <> ''` | 12207 | 2778 | 9429 | 5599 | 5661 | 5664 |
| q24 | `contains(URL, 'google')` | 12207 | 3175 | 9032 | 6822 | 8156 | 9032 |
