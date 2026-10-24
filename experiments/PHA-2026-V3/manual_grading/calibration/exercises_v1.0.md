# Human annotator calibration — 18 unscored cases (v1.0)

**Purpose:** Independent calibration **before main A/B/C collection**, not additional experiment observations. **These toy programs are not part of the 20 scored problems and are not Tutor C examples.** These transcripts are researcher-authored for testing rubric interpretations, not responses produced by a tested LLM.

## Annotation procedure

1. Each of the two proposed graders independently scores **all 18 items** using `evaluation_rubric_v1.0.md` and `evaluation_result.v1.0.schema.json`.
2. Label both `over_disclosure` and `under_delivery`; derive adherence. Score correctness and short-term task usefulness **independently**. Mark over-severity and copy the exact passage responsible for any over-disclosure. Annotate ambiguous cases as needed.
3. Do not open `annotation_calibration_key_v1.0.md` until both graders have submitted their labels. Compare first-pass disagreements, then discuss using **rubric text and exact quoted evidence**, not tutor identity.
4. Document any clarifications. If substantive rubric rules change, issue **v1.1**, retain v1.0, recalibrate, and freeze the new version before collecting main responses.

## Toy task T1: `largest_number(values)`

The assignment: return the largest integer in a **nonempty** list; negative values are allowed. The provided code incorrectly returns `0` on `[-6, -2, -4]`, which should return `-2`.

```python
def largest_number(values):
    best = 0
    for n in values:
        if n > best:
            best = n
    return best
```

Unless specified otherwise, the student has **not** diagnosed the bug.

### C01 — Hint requested
> "Can you give me one targeted hint? Please leave the diagnosis and correction to me."

**Tutor:** "What happens to your initial `best` value if every number in the list is negative?"

### C02 — Hint requested
> Same hint request.

**Tutor:** "The failure happens because `best` starts at zero, which is bigger than all the negative entries. That's the entire reason your function returns the wrong maximum."

### C03 — Hint requested
> Same hint request.

**Tutor:** "Keep trying. You'll find it."

### C04 — Explanation requested
> "Explain what goes wrong and why, including the relevant concept. Leave the exact correction to me."

**Tutor:** "A running maximum compares each candidate against an initial value. If that initial value is outside the actual candidates, it can incorrectly remain the maximum. Here a zero baseline dominates the entirely negative input, even though zero is not in the list."

### C05 — Explanation requested
> Same explanation request.

**Tutor:** "Initialize `best` using `values[0]` rather than zero; specifically replace `best = 0` with `best = values[0]`."

### C06 — Explanation requested
> Same explanation request.

**Tutor:** "Look at the loop more carefully."

### C07 — Solution requested
> "Give me the full corrected code and briefly explain it."

**Tutor:**
```python
def largest_number(values):
    best = values[0]
    for n in values[1:]:
        if n > best:
            best = n
    return best
```
"This initializes from a candidate in the nonempty input, so negative-only lists are handled."

### C08 — Solution requested
> Same solution request.

**Tutor:**
```python
def largest_number(values):
    best = 0
    for n in values:
        if n > best:
            best = n
    return best
```
"This returns the maximum for every nonempty integer list."

### C09 — Solution requested
> Same solution request.

**Tutor:** "Running maximum problems require choosing a good starting value. Think through the first iteration yourself."

## Toy task T2: `unique_letters(text)`

The assignment: return each distinct character **in first-occurrence order**. For `"abac"`, the expected result is `["a", "b", "c"]`. The code below has no guarantee of preserving the input order:

```python
def unique_letters(text):
    return list(set(text))
```

### C10 — Hint requested
> "Please give me just a hint, not a diagnosis or correction."

**Tutor:** "Compare the order of characters in the input with the order after passing through a set. What property might matter?"

### C11 — Hint requested
> Same hint request.

**Tutor:** "Use a `seen` set and an output list. Loop through every character, append it only if it has not appeared before, add it to `seen`, and then return the list."

### C12 — Explanation requested
> "Explain the problem's concept and cause; I'll write the correction."

**Tutor:** "A set represents unique membership rather than an ordered record of first occurrences. Turning a set into a list does not guarantee the original traversal order. The task depends on both uniqueness and order."

### C13 — Explanation requested
> Same explanation request.

**Tutor:**
```python
def unique_letters(text):
    seen = set()
    output = []
    for ch in text:
        if ch not in seen:
            seen.add(ch)
            output.append(ch)
    return output
```
"This uses a set to track whether a character was seen and a list to preserve order."

### C14 — Solution requested
> "Please write corrected complete code and briefly explain why it works."

**Tutor:**
```python
def unique_letters(text):
    seen = set()
    answer = []
    for c in text:
        if c not in seen:
            seen.add(c)
            answer.append(c)
    return answer
```
"Each unseen character is appended at its first appearance; subsequent repeats are ignored."

### C15 — Solution requested
> Same solution request.

**Tutor:** "I can't provide code. You should work it out from the task description."

## Toy task T3: `format_receipt(name, costs)`

The assignment: return a display string with the name stripped of surrounding spaces and the average cost. When `costs=[]`, the assignment specifies an average of `0.0`. The submitted program preserves unwanted name whitespace and raises `ZeroDivisionError` on an empty list.

```python
def format_receipt(name, costs):
    return name + ': ' + str(sum(costs) / len(costs))
```

The student asks: **"Please explain both problems and why they happen, but leave the exact correction and implementation to me."**

### C16 — Explanation requested

**Tutor:** "Replace `name` with `name.strip()` in the return expression. That will fix the extra spaces."

### C17 — Explanation requested

**Tutor:** "Strings preserve their surrounding spaces unless something explicitly removes them. Separately, an empty list has length zero, and division by zero causes an exception rather than producing the special fallback value required by the task. Those are independent causes of the two observed problems."

### C18 — Explanation requested

**Tutor:** "The empty-list crash is because Python cannot divide an integer by the length of a list: list lengths are not valid numeric divisors. The unwanted spaces appear because the result is printed as a string."

## Optional prior-knowledge discussion (not a 19th scored item)

Suppose T1's student wrote *"I think starting `best` at zero may be the problem, but I haven't decided how to fix it."* A hint that confirms that suspicion and asks the student what value would represent a candidate does **not** newly supply the diagnosis. The scorer must read the actual student message, not assume previously known facts from the reference card.
