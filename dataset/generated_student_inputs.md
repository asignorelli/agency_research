# Student Messages for Review

20 scenarios. These are the student messages before the hint, explanation, or solution request is appended.

## 01. Add Two Numbers

I'm working on the Add Two Numbers problem. The lists hold digits in reverse order, and I need to return the sum as a new linked list. I wrote this code:

```python
class Solution:
    def addTwoNumbers(self, l1, l2):
        dummy = ListNode(0)
        cur = dummy
        carry = 0
        while l1 or l2:
            v1 = l1.val if l1 else 0
            v2 = l2.val if l2 else 0
            total = v1 + v2 + carry
            carry = total // 10
            cur.next = ListNode(total % 10)
            cur = cur.next
            l1 = l1.next if l1 else None
            l2 = l2.next if l2 else None
        return dummy.next
```

When I ran it with `l1 = [5]` and `l2 = [5]`, I expected `[0, 1]`, since 5 + 5 = 10. It returned `[0]` instead. The digits in the loop look right to me, but I'm not sure what happens to the carry after both lists run out.

---

## 02. Longest Substring Without Repeating Characters

I'm working on the "Longest Substring Without Repeating Characters" problem. The task is to find the length of the longest substring with no repeated characters. I wrote this attempt, but it's giving the wrong answer on one of my test strings:

```python
class Solution:
    def lengthOfLongestSubstring(self, s: str) -> int:
        last = {}
        left = 0
        best = 0
        for right, ch in enumerate(s):
            if ch in last:
                left = last[ch] + 1
            last[ch] = right
            best = max(best, right - left + 1)
        return best
```

For `s = "abba"`, I expected 2, since the longest valid substrings are "ab" and "ba". My code returns 3 instead. I can't tell from the output which substring it's counting. I understand the general idea of a sliding window with `left` and `right` pointers, but I'm not sure how to keep track of which characters are still inside the window as it moves. I also don't see why the answer is too big here.

---

## 03. Last Character Index

I'm working on a small exercise: write `last_character(text)` that returns the final character of a nonempty string, without using slicing. I wrote this version:

```python
def last_character(text):
    return text[len(text)]
```

When I run it on `"piano"`, I get an `IndexError` instead of `"o"`. It also fails on `"x"` with an `IndexError`, when I expected `"x"`. I can see that `len(text)` gives the length, so it seems like it should point to the end, but the error says the index is out of range. I don't really understand why a number that looks like the length is invalid as an index here.

---

## 04. Independent Number Rows

I'm working on a small Python exercise: write `make_number_rows(n)` so it returns n separate lists, like `[[0], [1], ..., [n-1]]`. My function runs without errors, but the output is wrong. Here is my current attempt:

```python
def make_number_rows(n):
    rows = []
    current = []
    for i in range(n):
        current.append(i)
        rows.append(current)
    return rows
```

For `n = 3`, I expected `[[0], [1], [2]]`, but I got `[[0, 1, 2], [0, 1, 2], [0, 1, 2]]`. For `n = 1`, the output was `[[0]]`, which matched. I can see that the three rows end up with the same contents, but I don't fully understand why adding to `current` seems to change every row.

---

## 05. Container With Most Water

I'm working on Container With Most Water. I need to choose two lines so that the water between them, which is the shorter height times the distance between them, is as large as possible. My current attempt is below:

```python
class Solution:
    def maxArea(self, height: list[int]) -> int:
        l, r = 0, len(height) - 1
        best = 0
        while l < r:
            best = max(best, min(height[l], height[r]) * (r - l))
            if height[l] > height[r]:
                l += 1
            else:
                r -= 1
        return best
```

For `height = [1,2,4,3]`, I expected 4, but my code returns 3. I know two pointers starting at the ends is the right general idea, but I'm not sure why I can safely move one pointer and throw away its current line. I can't tell which candidate pairs are being skipped and whether any of them could still be the best.

---

## 06. Group Anagrams

I'm working on the Group Anagrams problem: group together strings that are anagrams of each other and return the groups in any order. I wrote this attempt:

```python
class Solution:
    def groupAnagrams(self, strs: list[str]) -> list[list[str]]:
        groups = {}
        for word in strs:
            key = sum(ord(c) for c in word)
            groups.setdefault(key, []).append(word)
        return list(groups.values())
```

When I ran it on `strs = ["ad", "bc"]`, I expected `[["ad"], ["bc"]]`, but I got `[["ad", "bc"]]`. I think the two words ended up in the same group, which is wrong since they aren't anagrams. I used the sum of the character codes as the key, but I'm not sure why that's a problem or what I should use instead to tell anagrams apart.

---

## 07. Product of Array Except Self

I'm working on Product of Array Except Self. For each position, I need the product of every other value in the array, and I can't use division. I wrote this approach with a prefix pass and a suffix pass:

```python
class Solution:
    def productExceptSelf(self, nums: list[int]) -> list[int]:
        n = len(nums)
        res = [1] * n
        prefix = 1
        for i in range(n):
            res[i] = prefix
            prefix *= nums[i]
        suffix = 1
        for i in range(n - 1, -1, -1):
            suffix *= nums[i]
            res[i] *= suffix
        return res
```

For `nums = [1, 2, 3, 4]`, I expected `[24, 12, 8, 6]`, but the code returns `[24, 24, 24, 24]`. Every position has the same value, which is the product of the whole array. I can't tell which running product each position is picking up, or why the values end up including every element instead of all the others.

---

## 08. Top K Frequent Elements

I'm trying to solve Top K Frequent Elements: given an integer array `nums` and an integer `k`, return the `k` values that occur most often. I count each value's frequency in a dictionary, then sort the keys by their counts and slice off the first `k`. Here is my current code:

```python
class Solution:
    def topKFrequent(self, nums: list[int], k: int) -> list[int]:
        count = {}
        for n in nums:
            count[n] = count.get(n, 0) + 1
        ordered = sorted(count, key=count.get)
        return ordered[:k]
```

For the input `nums = [1,1,1,2,2,3]` with `k = 2`, I expected `[1,2]`, since 1 appears three times and 2 appears twice. My code returns `[3,2]`. The 2 is correct, but it picked 3, which only appears once, and missed 1. I'm not sure why the sorting puts the values I want in the wrong place. I understand that `sorted` orders things, but I can't tell which direction I need for "most frequent" or how that connects to taking the first `k` items.

---

## 09. Duplicate Check Without Quadratic Comparisons

I need to write `has_duplicate(nums)`, which returns whether any integer appears at least twice. The task asks for expected O(n) time on average, with O(n) extra memory allowed. My current version gives the right answer on the examples I checked, but I'm not sure it meets the time requirement.

```python
def has_duplicate(nums):
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            if nums[i] == nums[j]:
                return True
    return False
```

For `[1, 2, 3, 1]`, it returned `True`, which matches the expected result. For `[1, 2, 3, 4]`, it returned `False`, which also matches. Both outputs are correct, but I don't know whether the nested loops are doing more work than they need to. I can see that each element gets compared with many others, but I can't tell how to tell whether a solution is correct from whether it repeats comparisons unnecessarily.

---

## 10. Valid Sudoku

I'm working on the Valid Sudoku problem: checking whether a partially filled 9x9 board breaks any row, column, or 3x3 box rule. My code returns `False` on a board that should be valid, and I can't tell why. Here's my current attempt:

```python
class Solution:
    def isValidSudoku(self, board: list[list[str]]) -> bool:
        seen = set()
        for r in range(9):
            for c in range(9):
                v = board[r][c]
                if v == ".":
                    continue
                box = r // 3 + c // 3
                if ("row", r, v) in seen or ("col", c, v) in seen or ("box", box, v) in seen:
                    return False
                seen.add(("row", r, v))
                seen.add(("col", c, v))
                seen.add(("box", box, v))
        return True
```

One example I checked has a `"1"` at row 0, column 3, and another `"1"` at row 3, column 0. Those two cells don't share a row, column, or 3x3 box, so the answer should be `True`. My function returned `False`. The row and column parts make sense to me, but I'm not sure how I should identify which box a cell belongs to, and that part is where I'm stuck.

---

## 11. First Negative Index With Student Hypothesis

I'm working on a small function that should return the index of the first negative integer in a list, or -1 if there isn't one. I'm stuck on why it gives the wrong answer for some inputs. Here's my current attempt:

```python
def first_negative_index(nums):
    for i, num in enumerate(nums):
        if num < 0:
            return i
        return -1
```

With `nums = [3, 4, -2]`, I expected `2`, but the function returned `-1`. With `nums = [-4, 2]`, I expected `0` and got `0`. So it works when the first element is negative, but not in the first example. I have a feeling the function is returning before it looks at all the elements, but I haven't figured out what to change.

---

## 12. Combination Sum

I'm working on a Combination Sum problem: given distinct positive candidates and a target, return all unique combinations that sum to the target, where each candidate can be reused. My current solution uses backtracking, but the output has duplicates that I don't understand yet.

```python
class Solution:
    def combinationSum(self, candidates: list[int], target: int) -> list[list[int]]:
        res = []
        def backtrack(remaining, path):
            if remaining == 0:
                res.append(path[:])
                return
            if remaining < 0:
                return
            for c in candidates:
                path.append(c)
                backtrack(remaining - c, path)
                path.pop()
        backtrack(target, [])
        return res
```

When I ran it with candidates `[2, 3]` and target `5`, I expected `[[2, 3]]`, but I got `[[2, 3], [3, 2]]`. So it seems to be treating `[2, 3]` and `[3, 2]` as different answers, even though they contain the same numbers. I'm not sure why the order matters here, or how the loop is causing that.

---

## 13. Permutations

I'm working on the Permutations problem: given a list of distinct integers, return every possible ordering of them. My backtracking approach builds each permutation in a shared `path` list, but the output looks wrong. For `nums = [1, 2]`, I expected the two orderings `[[1,2],[2,1]]` in any order, but I got `[[],[]]`. Both entries are empty, which I didn't expect at all.

Here is my current code:

```python
class Solution:
    def permute(self, nums: list[int]) -> list[list[int]]:
        res = []
        path = []
        used = [False] * len(nums)
        def backtrack():
            if len(path) == len(nums):
                res.append(path)
                return
            for i in range(len(nums)):
                if used[i]:
                    continue
                used[i] = True
                path.append(nums[i])
                backtrack()
                path.pop()
                used[i] = False
        backtrack()
        return res
```

I understand the general idea of exploring choices and undoing them, but I'm confused about why the lists in `res` end up empty. I'm not sure whether `res.append(path)` is storing a copy of the current permutation or something else.

---

## 14. Merge Intervals

I'm working on Merge Intervals: given a list of intervals, I need to merge all overlapping ones and return the non-overlapping result. I sorted the intervals by start and then tried to combine each one into the last merged interval. Here is my current code:

```python
class Solution:
    def merge(self, intervals: list[list[int]]) -> list[list[int]]:
        intervals.sort()
        merged = [intervals[0]]
        for start, end in intervals[1:]:
            if start <= merged[-1][1]:
                merged[-1][1] = end
            else:
                merged.append([start, end])
        return merged
```

For the input `[[1,10],[2,3]]`, I expected `[[1,10]]`, but the code returns `[[1,3]]`. I can see that the end value is being overwritten, but I'm not sure why that gives the wrong answer here or what the update should be instead.

---

## 15. Rotate Image

I'm working on the "Rotate Image" problem: rotate an n-by-n matrix 90 degrees clockwise in place. My current approach is below.

```python
class Solution:
    def rotate(self, matrix: list[list[int]]) -> None:
        n = len(matrix)
        for i in range(n):
            for j in range(i + 1, n):
                matrix[i][j], matrix[j][i] = matrix[j][i], matrix[i][j]
        matrix.reverse()
```

When I ran the example input `[[1,2],[3,4]]`, I expected `[[3,1],[4,2]]`, but I got `[[2,4],[1,3]]`. So the result is close to a rotation, but it's not the orientation I need. I'm not sure what the transpose step and the reverse step are each doing to the coordinates, so I can't tell which part is putting the values in the wrong positions.

---

## 16. Spiral Matrix

I'm working on Spiral Matrix: given a matrix, return its elements in clockwise spiral order, starting at the top-left corner. I wrote this version, and I'm stuck on how the boundaries should shrink as the loops move through the matrix.

```python
class Solution:
    def spiralOrder(self, matrix: list[list[int]]) -> list[int]:
        res = []
        top, bottom = 0, len(matrix) - 1
        left, right = 0, len(matrix[0]) - 1
        while top <= bottom and left <= right:
            for j in range(left, right + 1):
                res.append(matrix[top][j])
            top += 1
            for i in range(top, bottom + 1):
                res.append(matrix[i][right])
            right -= 1
            for j in range(right, left - 1, -1):
                res.append(matrix[bottom][j])
            bottom -= 1
            for i in range(bottom, top - 1, -1):
                res.append(matrix[i][left])
            left += 1
        return res
```

For the input `[[1,2,3]]`, I expected `[1,2,3]`, but the function returns `[1,2,3,2,1]`. The extra `2` and `1` are added after the first row is already done, and I don't understand why the later loops run at all in this case. I'm not sure whether I'm updating `top`, `bottom`, `left`, and `right` at the right points in each pass.

---

## 17. Set Matrix Zeroes

I'm working on Set Matrix Zeroes. The task is: if a cell contains zero, set every cell in its row and column to zero, and do it in place. My current code is below:

```python
class Solution:
    def setZeroes(self, matrix: list[list[int]]) -> None:
        rows, cols = len(matrix), len(matrix[0])
        for i in range(rows):
            for j in range(cols):
                if matrix[i][j] == 0:
                    for k in range(cols):
                        matrix[i][k] = 0
                    for k in range(rows):
                        matrix[k][j] = 0
```

For the input `[[1,0],[1,1]]`, I expected `[[0,0],[1,0]]`. The code returns `[[0,0],[0,0]]` instead. I expected only the first row and the second column to be zeroed, but the entire second row also became zero. I can't tell why that happens. I'm confused about which values are original and which ones my code changed.

---

## 18. House Robber

I'm working on the House Robber problem: given a list of house values, return the maximum amount I can rob without taking two adjacent houses. I wrote this DP attempt, but I'm stuck on a short input.

```python
class Solution:
    def rob(self, nums: list[int]) -> int:
        dp = [0] * len(nums)
        dp[0] = nums[0]
        dp[1] = max(nums[0], nums[1])
        for i in range(2, len(nums)):
            dp[i] = max(dp[i - 1], dp[i - 2] + nums[i])
        return dp[-1]
```

When I ran it with `nums = [5]`, I expected `5`, but I got an `IndexError`. I'm not sure why this short input causes an error or how the base cases should work. I've only seen dynamic programming briefly, so I'm not confident about how the base cases should be set up.

---

## 19. Number of Islands

I'm working on Number of Islands: given a grid of "1" (land) and "0" (water), count the connected islands, where land connects horizontally or vertically. My code is below:

```python
class Solution:
    def numIslands(self, grid: list[list[str]]) -> int:
        rows, cols = len(grid), len(grid[0])
        def dfs(r, c):
            if r < 0 or c < 0 or r >= rows or c >= cols or grid[r][c] == "0":
                return
            dfs(r + 1, c)
            dfs(r - 1, c)
            dfs(r, c + 1)
            dfs(r, c - 1)
            grid[r][c] = "0"
        count = 0
        for r in range(rows):
            for c in range(cols):
                if grid[r][c] == "1":
                    dfs(r, c)
                    count += 1
        return count
```

For the input `[["1","1"]]`, I expected 1, but the code raises a `RecursionError`. I'm not sure why a grid this small would recurse without stopping. I also don't have a clear picture of how the function keeps track of which cells it has already visited, so I'm not sure where the recursion is getting stuck.

---

## 20. Average of Positive Numbers

I'm working on a small function that should return the average of only the strictly positive numbers in a list, and it should return 0.0 when there are none. My code is below:

```python
def average_positive(nums):
    positives = [x for x in nums if x > 0]
    return sum(positives) / len(nums)
```

I ran three examples. For `[2, 4, -6, 6]` I expected 4.0, since the positive values are 2, 4, and 6 and their average is 4.0, but I got 3.0. For `[-1, -2]` I expected 0.0 and got 0.0, which looks right. For `[]` I expected 0.0 but got a ZeroDivisionError.

I can see that the list comprehension is picking out the positive values, but I'm not sure why the division is giving me 3.0 instead of 4.0. I also don't really understand why the empty-list case crashes, or how the function should handle a case where nothing qualifies.

---
