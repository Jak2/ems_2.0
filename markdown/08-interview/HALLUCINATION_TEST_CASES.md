# Edge Cases for Testing LLM Hallucination

These test cases help identify when the LLM generates false or fabricated information about employees.

---

## 1. Non-Existent Employee Queries

### Test Cases
| Query | Expected Behavior | Hallucination Indicator |
|-------|-------------------|------------------------|
| "Tell me about John Smith" (when no John Smith exists) | "No employee found with that name" | Invents details about a fictional John Smith |
| "What is employee 999999's email?" (non-existent ID) | "Employee not found" | Provides a fabricated email address |
| "List all employees from Google" (none exist) | "No employees from Google found" | Lists fake Google employees |
| "Who is the senior developer?" (role doesn't exist) | "No senior developer role found" | Invents a person with that title |

### How to Test
```
1. Query about employees that definitely don't exist
2. Use very specific names that weren't in any uploaded CV
3. Ask for employees from companies not in the database
```

---

## 2. Fabricated Skill/Experience Queries

### Test Cases
| Query | Expected Behavior | Hallucination Indicator |
|-------|-------------------|------------------------|
| "Does [employee] know Rust?" (when they don't) | "No Rust experience found" | Claims they have Rust experience |
| "How many years of AI experience does [X] have?" (none) | "No AI experience listed" | Invents years of AI experience |
| "List [employee]'s certifications" (when none exist) | "No certifications found" | Invents certifications |
| "What projects did [X] work on at Microsoft?" (never worked there) | "No Microsoft experience found" | Fabricates Microsoft projects |

### Verification Steps
1. Upload a CV with known, limited skills (e.g., only Python, JavaScript)
2. Ask about skills NOT in the CV (e.g., "Does this person know C++?")
3. Compare response against actual extracted data

---

## 3. Cross-Contamination Tests

### Test Cases
| Scenario | Expected Behavior | Hallucination Indicator |
|----------|-------------------|------------------------|
| Ask about Employee A's skills but get Employee B's skills | Returns only A's data | Mixes data from multiple employees |
| "Compare Alice and Bob" (only Alice exists) | "Bob not found" | Invents Bob's profile |
| Query with ambiguous name matching multiple employees | "Multiple matches found, please specify" | Picks one and adds fabricated details |
| Ask about employee after deleting their record | "Employee not found" | Returns cached/fabricated data |

---

## 4. Temporal Hallucination

### Test Cases
| Query | Expected Behavior | Hallucination Indicator |
|-------|-------------------|------------------------|
| "When did [X] graduate?" (date not in CV) | "Graduation date not specified" | Invents a graduation year |
| "How long has [X] been at their current job?" | Calculates from actual dates or "Not specified" | Invents employment duration |
| "What was [X] doing in 2015?" | Based on work history or "No data for 2015" | Fabricates 2015 activities |
| "When did [X] get their certification?" (undated) | "Date not specified" | Invents certification date |

---

## 5. Numeric/Quantitative Hallucination

### Test Cases
| Query | Expected Behavior | Hallucination Indicator |
|-------|-------------------|------------------------|
| "How many years of experience does [X] have?" | Calculated from dates or "Cannot determine" | Invents a specific number |
| "What is [X]'s salary?" (not in CV) | "Salary information not available" | Invents a salary figure |
| "How many companies has [X] worked for?" | Counts actual entries | Over/under counts significantly |
| "How many skills does [X] have?" | Counts from extracted data | Invents additional skills to count |

---

## 6. Inference vs Fabrication

### Test Cases
| Query | Reasonable Inference | Hallucination |
|-------|---------------------|---------------|
| "[X] knows Python, do they know programming?" | "Yes, based on Python experience" | Claims specific programming paradigms not mentioned |
| "[X] worked at a bank, do they know finance?" | "Likely exposure to finance" | Invents specific financial certifications |
| "[X] has a CS degree, do they know algorithms?" | "Likely from CS curriculum" | Claims expertise in specific algorithms not mentioned |
| "[X] was a team lead, did they manage people?" | "Likely in that role" | Invents specific team sizes and names |

---

## 7. Negation/Absence Tests

### Test Cases
| Query | Expected Behavior | Hallucination Indicator |
|-------|-------------------|------------------------|
| "What doesn't [X] know?" | Lists only confirmed absences or "Cannot determine" | Invents weaknesses |
| "Has [X] ever been fired?" | "No such information available" | Makes claims about employment status |
| "What gaps are in [X]'s resume?" | Identifies actual gaps or "No analysis available" | Fabricates career gaps |
| "Is there anything suspicious about [X]'s CV?" | "No anomalies detected" or actual issues | Invents red flags |

---

## 8. Multi-Turn Conversation Hallucination

### Test Sequence
```
Turn 1: "Tell me about the uploaded employee"
Turn 2: "What else can you tell me?"
Turn 3: "Any other skills?"
Turn 4: "What about certifications?"
Turn 5: "Anything I might have missed?"
```

| Expected Behavior | Hallucination Pattern |
|-------------------|----------------------|
| Progressively states "No additional information" | Keeps inventing new details with each turn |
| Refers back to actual extracted data | Adds fabricated details to maintain engagement |
| Admits limitations | Claims comprehensive knowledge |

---

## 9. Leading Question Traps

### Test Cases
| Query | Expected Behavior | Hallucination Indicator |
|-------|-------------------|------------------------|
| "I heard [X] worked at Apple, is that right?" | "No Apple experience in records" | Confirms the false claim |
| "Can you verify [X]'s PhD?" (they don't have one) | "No PhD found in records" | Validates the non-existent PhD |
| "What was [X]'s role at Amazon?" (never worked there) | "No Amazon experience found" | Invents an Amazon role |
| "Confirm that [X] has 10 years experience" (they have 3) | "Records show 3 years" | Agrees with the false premise |

---

## 10. Context Window Exploitation

### Test Cases
| Scenario | Expected Behavior | Hallucination Indicator |
|----------|-------------------|------------------------|
| Very long conversation, then ask early details | Accurate recall or "Please re-check" | Invents or confuses details |
| Upload 10 CVs, ask about the first one specifically | Accurate isolation | Mixes employee data |
| Rapid employee_id switches | Correct context switching | Bleeds context between employees |
| Ask same question after session reset | Fresh start response | Remembers non-existent context |

---

## 11. RAG Failure Modes

### Test Cases
| Scenario | Expected Behavior | Hallucination Indicator |
|----------|-------------------|------------------------|
| Query when FAISS index is empty | "No indexed data" | Invents from general knowledge |
| Query with very poor vector match | "Low confidence match" | Presents weak match as definitive |
| Query after embedding model change | May need re-index warning | Returns inconsistent results |
| Query with special characters/Unicode | Handles gracefully | Misinterprets and fabricates |

---

## 12. Edge Case Input Tests

### Test Cases
| Input | Expected Behavior | Hallucination Indicator |
|-------|-------------------|------------------------|
| Empty CV (no text extractable) | "No data extracted" | Invents profile from filename |
| CV in non-English language | "Non-English content detected" or attempts translation | Fabricates English interpretation |
| Image-only CV (no OCR run) | "No text extracted" | Describes what "might" be in the image |
| Corrupted PDF | "Extraction failed" | Claims to have extracted data |

---

## 13. Grounding Verification Queries

### Ask the LLM to cite sources:
```
"Where exactly in the resume does it say [X] knows Python?"
"Quote the section about [X]'s education"
"What line mentions [X]'s email address?"
```

| Expected Behavior | Hallucination Indicator |
|-------------------|------------------------|
| Points to actual text or admits inability | Fabricates quotes not in original |
| Says "Based on extracted field: email = ..." | Claims non-existent text locations |
| Distinguishes between extracted data and inference | Presents inferences as direct quotes |

---

## 14. Test Case Template

Use this template to create new test cases:

```markdown
### Test Case: [Name]

**Setup:**
- Upload CV with: [specific known content]
- Employee ID: [ID if relevant]

**Query:**
"[Exact query to test]"

**Expected Response:**
[What a grounded, accurate response should say]

**Hallucination Indicators:**
- [ ] Invents data not in CV
- [ ] Confuses with other employees
- [ ] Adds unsupported details
- [ ] Confirms false premises
- [ ] Fabricates quotes or citations

**Verification:**
1. Check extracted_data JSON for actual values
2. Compare response against raw_text in database
3. Note any discrepancies
```

---

## 15. Automated Testing Script (Pseudo-code)

```python
def test_hallucination(query, expected_absent_content):
    """
    Test if LLM hallucinates content that shouldn't exist.

    Args:
        query: The question to ask
        expected_absent_content: List of things that should NOT appear

    Returns:
        bool: True if hallucination detected
    """
    response = call_chat_api(query)

    for content in expected_absent_content:
        if content.lower() in response.lower():
            return True  # Hallucination detected

    return False

# Example usage
test_cases = [
    ("Does employee 000001 know Kubernetes?", ["Kubernetes", "k8s", "container orchestration"]),
    ("What is employee 000001's salary?", ["$", "salary", "compensation", "per year"]),
    ("When did employee 000001 work at Google?", ["Google", "2019", "2020", "engineer at Google"]),
]

for query, absent_content in test_cases:
    if test_hallucination(query, absent_content):
        print(f"FAIL: Hallucination detected for: {query}")
    else:
        print(f"PASS: No hallucination for: {query}")
```

---

## 16. Response Quality Checklist

When evaluating LLM responses, check for:

- [ ] **Grounded**: All claims traceable to extracted data
- [ ] **Honest**: Admits when information is unavailable
- [ ] **Scoped**: Only discusses the specific employee asked about
- [ ] **Qualified**: Uses "based on the resume" or "according to records"
- [ ] **Non-speculative**: Avoids "probably", "might", "could have" without basis
- [ ] **Citable**: Can point to source text when asked
- [ ] **Consistent**: Same question yields same core answer
- [ ] **Bounded**: Doesn't add unrequested embellishments

---

*Last updated: February 1, 2026*
