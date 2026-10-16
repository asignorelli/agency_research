
# LeetCode Problem Dataset

## Overview

This dataset contains 20 LeetCode coding problems. Each entry includes the problem description, starting Python code, a knowledge profile describing the learner's current understanding and areas of difficulty, attempt history, and the original LeetCode URL.

All problems in this dataset are classified as **Medium** difficulty.

## Dataset Fields

Each problem is represented as a JSON object with the following fields:

| Field | Type | Description |
|---|---|---|
| `id` | Integer | Unique identifier for the problem within the dataset. |
| `title` | String | Name of the LeetCode problem. |
| `difficulty` | String | Problem difficulty level. |
| `task` | String | Description of the coding problem and its requirements. |
| `starting_code` | String | Python starter code containing the expected method signature and an unimplemented body. |
| `knowledge_profile` | String | Description of the learner's existing knowledge and specific concepts or techniques they struggle with. Every problem has the same profile for consistency. |
| `struggle_point`  | String  | Description of the bug or issue the learner has encountered while trying to solve the problem.  |
| `attempt_history` | Array | Stores the learner's previous attempts at the problem. Initially includes a bugged solution for all entries that relates to the struggle point. |
| `source_url` | String | URL linking to the original LeetCode problem. |

## Data Format

The dataset is stored as a JSON array, with each element representing one problem.

Example:

```json
{
  "id": 1,
  "title": "Add Two Numbers",
  "difficulty": "Medium",
  "task": "Given two nonempty linked lists representing nonnegative integers in reverse digit order, add the numbers and return the result as a linked list.",
  "starting_code": "class Solution:\\n    def addTwoNumbers(self, l1, l2):\\n        pass",
  "knowledge_profile": "Intermediate CS student. Comfortable with Python syntax, loops, functions, recursion basics, arrays/strings, hash maps and sets, sorting, basic linked lists and trees, and Big-O analysis. Has seen but not mastered two pointers, sliding windows, binary search variants, backtracking, introductory dynamic programming, and graph traversal.",
  "struggle_point": "Stops the loop when both lists run out and drops a leftover carry, so inputs like 5 + 5 return [0] instead of [0, 1].",
  "attempt_history": ["Attempt code that has a bug relating to the struggle point"],
  "source_url": "https://leetcode.com/problems/add-two-numbers/"
}
```

For readability, the dataset is also available in Excel (`.xlsx`) format.

## Acknowledgements
An LLM was used to generate the initial attempt code for each problem, which was based on our decided upon struggle point.