
## 01. Add Two Numbers

I'm working on Add Two Numbers. The task is: Given two nonempty linked lists representing nonnegative integers in reverse digit order, add the numbers and return the result as a linked list. Here is my current attempt:

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

When I ran it with `l1 = [5]` and `l2 = [5]`, I expected `[0, 1]`, since 5 + 5 = 10, but it returned `[0]`. I'm not sure why the result isn't what I expected.

---

## 02. Longest Substring Without Repeating Characters

I'm working on Longest Substring Without Repeating Characters. The task is: Given a string, find the length of its longest substring containing no repeated characters. Here is my current attempt:

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

For `s = "abba"`, I expected `2`, but my code returns `3`. I'm not sure why the result isn't what I expected.

---

## 03. Longest Palindromic Substring

I'm working on Longest Palindromic Substring. The task is: Given a string, return its longest contiguous substring that reads the same forward and backward. Here is my current attempt:

```python
class Solution:
    def longestPalindrome(self, s: str) -> str:
        best = ""
        for center in range(len(s)):
            l, r = center, center
            while l >= 0 and r < len(s) and s[l] == s[r]:
                l -= 1
                r += 1
            if r - l - 1 > len(best):
                best = s[l + 1:r]
        return best
```

For `s = "cbbd"`, I expected `"bb"`, but my code returns `"c"`. I'm not sure why the result isn't what I expected.

---

## 04. 3Sum

I'm working on 3Sum. The task is: Given an integer array, find all unique triplets whose three values sum to zero. Here is my current attempt:

```python
class Solution:
    def threeSum(self, nums: list[int]) -> list[list[int]]:
        nums.sort()
        res = []
        for i in range(len(nums) - 2):
            if i > 0 and nums[i] == nums[i - 1]:
                continue
            l, r = i + 1, len(nums) - 1
            while l < r:
                total = nums[i] + nums[l] + nums[r]
                if total < 0:
                    l += 1
                elif total > 0:
                    r -= 1
                else:
                    res.append([nums[i], nums[l], nums[r]])
                    l += 1
                    r -= 1
        return res
```

For `nums = [-2, 0, 0, 2, 2]`, I expected `[[-2, 0, 2]]`, but my code returns `[[-2, 0, 2], [-2, 0, 2]]`. I'm not sure why the result isn't what I expected.

---

## 05. Container With Most Water

I'm working on Container With Most Water. The task is: Given heights representing vertical lines, choose two lines that together with the horizontal axis contain the greatest possible amount of water. Here is my current attempt:

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

For `height = [1,2,4,3]`, I expected `4`, but my code returns `3`. I'm not sure why the result isn't what I expected.

---

## 06. Group Anagrams

I'm working on Group Anagrams. The task is: Group together all strings that are anagrams of one another and return the groups in any order. Here is my current attempt:

```python
class Solution:
    def groupAnagrams(self, strs: list[str]) -> list[list[str]]:
        groups = {}
        for word in strs:
            key = sum(ord(c) for c in word)
            groups.setdefault(key, []).append(word)
        return list(groups.values())
```

When I ran it on `strs = ["ad", "bc"]`, I expected `[["ad"], ["bc"]]`, but I got `[["ad", "bc"]]`. I'm not sure why the result isn't what I expected.

---

## 07. Product of Array Except Self

I'm working on Product of Array Except Self. The task is: Return an array where each position contains the product of all input values except the value at that position, without using division. Here is my current attempt:

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

For `nums = [1, 2, 3, 4]`, I expected `[24, 12, 8, 6]`, but the code returns `[24, 24, 24, 24]`. I'm not sure why the result isn't what I expected.

---

## 08. Top K Frequent Elements

I'm working on Top K Frequent Elements. The task is: Given an integer array and an integer k, return the k values that occur most frequently. Here is my current attempt:

```python
class Solution:
    def topKFrequent(self, nums: list[int], k: int) -> list[int]:
        count = {}
        for n in nums:
            count[n] = count.get(n, 0) + 1
        ordered = sorted(count, key=count.get)
        return ordered[:k]
```

For `nums = [1,1,1,2,2,3]` with `k = 2`, I expected `[1,2]` (in any order), but my code returns `[3,2]`. I'm not sure why the result isn't what I expected.

---

## 09. Longest Consecutive Sequence

I'm working on Longest Consecutive Sequence. The task is: Given an unsorted integer array, find the length of its longest sequence of consecutive integer values in O(n) time. Here is my current attempt:

```python
class Solution:
    def longestConsecutive(self, nums: list[int]) -> int:
        seen = set(nums)
        best = 0
        for n in seen:
            cur = n
            length = 1
            while cur + 1 in seen:
                cur += 1
                length += 1
            best = max(best, length)
        return best
```

For `nums = [100, 4, 200, 1, 3, 2]`, my code returns `4`, which is correct. The task requires O(n) time, but I'm unsure whether my approach meets that requirement.

---

## 10. Valid Sudoku

I'm working on Valid Sudoku. The task is: Determine whether a partially filled 9-by-9 Sudoku board is valid according to row, column, and 3-by-3 box constraints. Here is my current attempt:

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

I tested it on this board, which has a `"1"` at row 0, column 3 and another `"1"` at row 3, column 0, with every other cell empty:

```python
board = [
    [".", ".", ".", "1", ".", ".", ".", ".", "."],
    [".", ".", ".", ".", ".", ".", ".", ".", "."],
    [".", ".", ".", ".", ".", ".", ".", ".", "."],
    ["1", ".", ".", ".", ".", ".", ".", ".", "."],
    [".", ".", ".", ".", ".", ".", ".", ".", "."],
    [".", ".", ".", ".", ".", ".", ".", ".", "."],
    [".", ".", ".", ".", ".", ".", ".", ".", "."],
    [".", ".", ".", ".", ".", ".", ".", ".", "."],
    [".", ".", ".", ".", ".", ".", ".", ".", "."]
]
```

Those two cells don't share a row, column, or 3x3 box, so I expected `True`, but my function returns `False`. I'm not sure why the result isn't what I expected.

---

## 11. Search in Rotated Sorted Array

I'm working on Search in Rotated Sorted Array. The task is: Search for a target in a rotated sorted array of distinct integers in O(log n) time. Return its index or -1 if absent. Here is my current attempt:

```python
class Solution:
    def search(self, nums: list[int], target: int) -> int:
        l, r = 0, len(nums) - 1
        while l <= r:
            mid = (l + r) // 2
            if nums[mid] == target:
                return mid
            if nums[l] <= nums[mid]:
                if nums[l] < target < nums[mid]:
                    r = mid - 1
                else:
                    l = mid + 1
            else:
                if nums[mid] < target < nums[r]:
                    l = mid + 1
                else:
                    r = mid - 1
        return -1
```

For `nums = [4,5,6,7,0,1,2]` and `target = 4`, I expected `0`, but my code returns `-1`. I'm not sure why the result isn't what I expected.

---

## 12. Combination Sum

I'm working on Combination Sum. The task is: Given distinct positive candidate numbers and a target, find all unique combinations whose values sum to the target. A candidate can be used repeatedly. Here is my current attempt:

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

When I ran it with `candidates = [2, 3]` and `target = 5`, I expected `[[2, 3]]`, but I got `[[2, 3], [3, 2]]`. I'm not sure why the result isn't what I expected.

---

## 13. Permutations

I'm working on Permutations. The task is: Given a list of distinct integers, return every possible ordering of those integers. Here is my current attempt:

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

For `nums = [1, 2]`, I expected `[[1,2],[2,1]]` in any order, but I got `[[],[]]`. I'm not sure why the result isn't what I expected.

---

## 14. Merge Intervals

I'm working on Merge Intervals. The task is: Given intervals, merge all overlapping intervals and return the resulting nonoverlapping intervals. Here is my current attempt:

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

For the input `[[1,10],[2,3]]`, I expected `[[1,10]]`, but the code returns `[[1,3]]`. I'm not sure why the result isn't what I expected.

---

## 15. Rotate Image

I'm working on Rotate Image. The task is: Rotate an n-by-n matrix 90 degrees clockwise in place. Here is my current attempt:

```python
class Solution:
    def rotate(self, matrix: list[list[int]]) -> None:
        n = len(matrix)
        for i in range(n):
            for j in range(i + 1, n):
                matrix[i][j], matrix[j][i] = matrix[j][i], matrix[i][j]
        matrix.reverse()
```

When I call `rotate(matrix)` with `matrix = [[1,2],[3,4]]`, I expected the matrix to become `[[3,1],[4,2]]`, but it becomes `[[2,4],[1,3]]`. I'm not sure why the result isn't what I expected.

---

## 16. Spiral Matrix

I'm working on Spiral Matrix. The task is: Given a matrix, return its elements in clockwise spiral order, starting at the top-left corner. Here is my current attempt:

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

For the input `[[1,2,3]]`, I expected `[1,2,3]`, but the function returns `[1,2,3,2,1]`. I'm not sure why the result isn't what I expected.

---

## 17. Set Matrix Zeroes

I'm working on Set Matrix Zeroes. The task is: If a matrix cell contains zero, set every cell in its row and column to zero. Modify the matrix in place. Here is my current attempt:

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

When I call `setZeroes(matrix)` with `matrix = [[1,0],[1,1]]`, I expected the matrix to become `[[0,0],[1,0]]`, but it becomes `[[0,0],[0,0]]`. I'm not sure why the result isn't what I expected.

---

## 18. House Robber

I'm working on House Robber. The task is: Given the amount of money in each house, determine the maximum amount that can be collected without robbing two adjacent houses. Here is my current attempt:

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

When I ran it with `nums = [5]`, I expected `5`, but I got an `IndexError`. I'm not sure why the result isn't what I expected.

---

## 19. Number of Islands

I'm working on Number of Islands. The task is: Given a grid of land and water cells, count the connected islands. Land cells connect horizontally or vertically. Here is my current attempt:

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

For the input `[["1","1"]]`, I expected `1`, but the code raises a `RecursionError`. I'm not sure why the result isn't what I expected.

---

## 20. Coin Change

I'm working on Coin Change. The task is: Given coin denominations and a target amount, return the minimum number of coins needed to make that amount, or -1 if it is impossible. Each denomination can be used unlimited times. Here is my current attempt:

```python
class Solution:
    def coinChange(self, coins: list[int], amount: int) -> int:
        dp = [float("inf")] * (amount + 1)
        dp[0] = 0
        for a in range(1, amount + 1):
            for c in coins:
                if a - c >= 0:
                    dp[a] = min(dp[a], dp[a - c] + 1)
        return dp[amount]
```

For `coins = [2]` and `amount = 3`, I expected `-1`, but my code returns `inf`. I'm not sure why the result isn't what I expected.

---
