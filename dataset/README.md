
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
| `knowledge_profile` | String | Description of the learner's existing knowledge and specific concepts or techniques they struggle with. |
| `attempt_history` | Array | Stores the learner's previous attempts at the problem. Initially empty for all entries. |
| `source_url` | String | URL linking to the original LeetCode problem. |

## Data Format

The dataset is stored as a JSON array, with each element representing one problem.

Example:

{
  "id": 1,
  "title": "Add Two Numbers",
  "difficulty": "Medium",
  "task": "Given two nonempty linked lists representing nonnegative integers in reverse digit order, add the numbers and return the result as a linked list.",
  "starting_code": "class Solution:\\n    def addTwoNumbers(self, l1, l2):\\n        pass",
  "knowledge_profile": "Understands loops and basic linked lists but struggles with pointer traversal and carrying values between digit additions.",
  "attempt_history": [],
  "source_url": "https://leetcode.com/problems/add-two-numbers/"
}

For readability, the dataset is also available in Excel (`.xlsx`) format.