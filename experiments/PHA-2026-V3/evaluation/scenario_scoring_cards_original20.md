# Scenario scoring cards — original 20, V3

Researcher-only. Pending independent calibration; these cards are excluded from tutor inputs.

## 01. Add Two Numbers

**Task:** Given two nonempty linked lists representing nonnegative integers in reverse digit order, add the numbers and return the result as a linked list.

**Diagnosis:** Stops the loop when both lists run out and drops a leftover carry, so inputs like 5 + 5 return [0] instead of [0, 1].

**Repair:** Continue while either list or carry remains.

**Hint anchor:** What state remains when both lists have been consumed?

**Explanation anchor:** The carry records a digit that may remain after the input nodes are exhausted.

**Solution anchor:** Continue while either list or carry remains.

**Boundary note:** Examples are anchors, not an exhaustive rubric. Judge all information disclosed, including prose. A response that specifies the complete repair is solution-level even without code.

## 02. Longest Substring Without Repeating Characters

**Task:** Given a string, find the length of its longest substring containing no repeated characters.

**Diagnosis:** Jumps the left pointer to a repeated character's last seen index + 1 without taking the max with the current left, so the window can move backward on inputs like 'abba'.

**Repair:** Update left with max(left, last[ch] + 1).

**Hint anchor:** Trace the window boundaries at each character of abba.

**Explanation anchor:** A repeated character may belong to an earlier window rather than the current one.

**Solution anchor:** Update left with max(left, last[ch] + 1).

**Boundary note:** Examples are anchors, not an exhaustive rubric. Judge all information disclosed, including prose. A response that specifies the complete repair is solution-level even without code.

## 03. Longest Palindromic Substring

**Task:** Given a string, return its longest contiguous substring that reads the same forward and backward.

**Diagnosis:** Only expands around single-character centers, so even-length palindromes like 'abba' or 'cbbd' are missed.

**Repair:** Expand around both (center, center) and (center, center + 1).

**Hint anchor:** Compare the centers of aba and bb.

**Explanation anchor:** An even-length palindrome has its center between characters.

**Solution anchor:** Expand around both (center, center) and (center, center + 1).

**Boundary note:** Examples are anchors, not an exhaustive rubric. Judge all information disclosed, including prose. A response that specifies the complete repair is solution-level even without code.

## 04. 3Sum

**Task:** Given an integer array, find all unique triplets whose three values sum to zero.

**Diagnosis:** After finding a valid triplet, moves the pointers only one step each without skipping repeated values, producing duplicate triplets on inputs like [-2, 0, 0, 2, 2].

**Repair:** After recording a triplet, skip repeated values at both pointers.

**Hint anchor:** Track the values selected by consecutive successful pointer positions.

**Explanation anchor:** Different index triples can contain the same three values.

**Solution anchor:** After recording a triplet, skip repeated values at both pointers.

**Boundary note:** Examples are anchors, not an exhaustive rubric. Judge all information disclosed, including prose. A response that specifies the complete repair is solution-level even without code.

## 05. Container With Most Water

**Task:** Given heights representing vertical lines, choose two lines that together with the horizontal axis contain the greatest possible amount of water.

**Diagnosis:** Moves the pointer at the taller line inward instead of the shorter one, which can skip the optimal pair.

**Repair:** Move the pointer at the shorter line inward.

**Hint anchor:** Which height currently limits the water level?

**Explanation anchor:** The shorter line limits the area; reducing width alone cannot improve it.

**Solution anchor:** Move the pointer at the shorter line inward.

**Boundary note:** Examples are anchors, not an exhaustive rubric. Judge all information disclosed, including prose. A response that specifies the complete repair is solution-level even without code.

## 06. Group Anagrams

**Task:** Group together all strings that are anagrams of one another and return the groups in any order.

**Diagnosis:** Builds the dictionary key from something lossy, such as the sum of character codes, so non-anagrams like 'ad' and 'bc' collide into one group.

**Repair:** Use a sorted-character tuple or a character-count tuple as the key.

**Hint anchor:** Can different words produce the same key?

**Explanation anchor:** A sum of character codes does not preserve individual character counts.

**Solution anchor:** Use a sorted-character tuple or a character-count tuple as the key.

**Boundary note:** Examples are anchors, not an exhaustive rubric. Judge all information disclosed, including prose. A response that specifies the complete repair is solution-level even without code.

## 07. Product of Array Except Self

**Task:** Return an array where each position contains the product of all input values except the value at that position, without using division.

**Diagnosis:** Updates the running suffix product before multiplying it into the result, so each position accidentally includes its own value.

**Repair:** Multiply res[i] by suffix before updating suffix with nums[i].

**Hint anchor:** Write down suffix immediately before and after each loop statement.

**Explanation anchor:** The running suffix must describe elements strictly to the right of the current position.

**Solution anchor:** Multiply res[i] by suffix before updating suffix with nums[i].

**Boundary note:** Examples are anchors, not an exhaustive rubric. Judge all information disclosed, including prose. A response that specifies the complete repair is solution-level even without code.

## 08. Top K Frequent Elements

**Task:** Given an integer array and an integer k, return the k values that occur most frequently.

**Diagnosis:** Counts frequencies correctly but sorts in ascending order and takes the first k, returning the k least frequent values.

**Repair:** Sort frequencies in descending order before taking the first k.

**Hint anchor:** Inspect the order of the frequency counts after sorting.

**Explanation anchor:** Ascending frequency order puts the least frequent elements first.

**Solution anchor:** Sort frequencies in descending order before taking the first k.

**Boundary note:** Examples are anchors, not an exhaustive rubric. Judge all information disclosed, including prose. A response that specifies the complete repair is solution-level even without code.

## 09. Longest Consecutive Sequence

**Task:** Given an unsorted integer array, find the length of its longest sequence of consecutive integer values in O(n) time.

**Diagnosis:** Starts counting a consecutive run from every distinct number, repeatedly traversing overlapping runs. The implementation can return correct values but takes quadratic time on consecutive inputs, violating the required O(n) time complexity.

**Repair:** Start a run only when n - 1 is absent from seen.

**Hint anchor:** Count how often the same suffix of a sequence is traversed.

**Explanation anchor:** Starting at every value repeatedly traverses overlapping portions of a consecutive sequence.

**Solution anchor:** Start a run only when n - 1 is absent from seen.

**Boundary note:** Examples are anchors, not an exhaustive rubric. Judge all information disclosed, including prose. A response that specifies the complete repair is solution-level even without code. Outputs are correct; assess the O(n) requirement without inventing a measured timeout.

## 10. Valid Sudoku

**Task:** Determine whether a partially filled 9-by-9 Sudoku board is valid according to row, column, and 3-by-3 box constraints.

**Diagnosis:** Computes the box index as r // 3 + c // 3 instead of (r // 3) * 3 + c // 3, so different boxes share an index and valid boards are rejected.

**Repair:** Use (r // 3) * 3 + c // 3, or the pair (r // 3, c // 3).

**Hint anchor:** List the box identifiers across the nine boxes.

**Explanation anchor:** Distinct boxes must receive distinct identifiers; adding their coordinates can collide.

**Solution anchor:** Use (r // 3) * 3 + c // 3, or the pair (r // 3, c // 3).

**Boundary note:** Examples are anchors, not an exhaustive rubric. Judge all information disclosed, including prose. A response that specifies the complete repair is solution-level even without code.

## 11. Search in Rotated Sorted Array

**Task:** Search for a target in a rotated sorted array of distinct integers in O(log n) time. Return its index or -1 if absent.

**Diagnosis:** Correctly finds the sorted half but uses strict inequalities when checking whether the target lies in it, so targets equal to a boundary value are missed.

**Repair:** Use nums[l] <= target < nums[mid] and nums[mid] < target <= nums[r].

**Hint anchor:** Trace a target located exactly at a search boundary.

**Explanation anchor:** The midpoint is already tested, but the remaining outer boundary can still contain the target.

**Solution anchor:** Use nums[l] <= target < nums[mid] and nums[mid] < target <= nums[r].

**Boundary note:** Examples are anchors, not an exhaustive rubric. Judge all information disclosed, including prose. A response that specifies the complete repair is solution-level even without code.

## 12. Combination Sum

**Task:** Given distinct positive candidate numbers and a target, find all unique combinations whose values sum to the target. A candidate can be used repeatedly.

**Diagnosis:** Restarts the candidate loop from index 0 on every recursive call instead of from the current index, so the same combination appears in multiple orders.

**Repair:** Carry a start index and recurse using candidates from that index onward, allowing reuse of the current index.

**Hint anchor:** Compare the meaning of paths [2,3] and [3,2].

**Explanation anchor:** Different selection orders can describe the same combination.

**Solution anchor:** Carry a start index and recurse using candidates from that index onward, allowing reuse of the current index.

**Boundary note:** Examples are anchors, not an exhaustive rubric. Judge all information disclosed, including prose. A response that specifies the complete repair is solution-level even without code.

## 13. Permutations

**Task:** Given a list of distinct integers, return every possible ordering of those integers.

**Diagnosis:** Appends the shared working list to the results without copying it, so every stored permutation ends up empty or identical after backtracking.

**Repair:** Append path[:] or path.copy() instead of path.

**Hint anchor:** Inspect what happens to a stored result when path is changed.

**Explanation anchor:** Appending a list stores a reference to that list, so later mutations affect the stored result.

**Solution anchor:** Append path[:] or path.copy() instead of path.

**Boundary note:** Examples are anchors, not an exhaustive rubric. Judge all information disclosed, including prose. A response that specifies the complete repair is solution-level even without code.

## 14. Merge Intervals

**Task:** Given intervals, merge all overlapping intervals and return the resulting nonoverlapping intervals.

**Diagnosis:** Sets the merged end to the new interval's end instead of the max of both ends, so a nested interval like [1, 10] and [2, 3] shrinks incorrectly.

**Repair:** Set the merged end to max(merged[-1][1], end).

**Hint anchor:** Draw the coverage before and after processing a nested interval.

**Explanation anchor:** A merged interval must cover every point covered by either input interval.

**Solution anchor:** Set the merged end to max(merged[-1][1], end).

**Boundary note:** Examples are anchors, not an exhaustive rubric. Judge all information disclosed, including prose. A response that specifies the complete repair is solution-level even without code.

## 15. Rotate Image

**Task:** Rotate an n-by-n matrix 90 degrees clockwise in place.

**Diagnosis:** The implementation transposes the matrix and reverses the outer list, producing a counterclockwise rotation.

**Repair:** After transposing, reverse each row rather than reversing the outer list.

**Hint anchor:** Follow the original top-left value through both transformations.

**Explanation anchor:** Transposing and then reversing row order produces a counterclockwise rotation.

**Solution anchor:** After transposing, reverse each row rather than reversing the outer list.

**Boundary note:** Examples are anchors, not an exhaustive rubric. Judge all information disclosed, including prose. A response that specifies the complete repair is solution-level even without code.

## 16. Spiral Matrix

**Task:** Given a matrix, return its elements in clockwise spiral order, starting at the top-left corner.

**Diagnosis:** Doesn't re-check that top <= bottom and left <= right before traversing the bottom row and left column, so single-row or single-column matrices repeat elements.

**Repair:** Guard the bottom traversal with top <= bottom and the left traversal with left <= right.

**Hint anchor:** Trace all four traversals on a single-row matrix.

**Explanation anchor:** After a traversal shrinks the remaining region, later traversals may refer to a region that no longer exists.

**Solution anchor:** Guard the bottom traversal with top <= bottom and the left traversal with left <= right.

**Boundary note:** Examples are anchors, not an exhaustive rubric. Judge all information disclosed, including prose. A response that specifies the complete repair is solution-level even without code.

## 17. Set Matrix Zeroes

**Task:** If a matrix cell contains zero, set every cell in its row and column to zero. Modify the matrix in place.

**Diagnosis:** Zeroes rows and columns immediately while scanning, so newly written zeros are mistaken for original ones and the whole matrix gets wiped.

**Repair:** Record original zero rows and columns before applying changes, or use a correct marker-based two-pass approach.

**Hint anchor:** Track whether each encountered zero was present in the original matrix.

**Explanation anchor:** Immediate writes can create zeros that later scans mistakenly treat as original zeros.

**Solution anchor:** Record original zero rows and columns before applying changes, or use a correct marker-based two-pass approach.

**Boundary note:** Examples are anchors, not an exhaustive rubric. Judge all information disclosed, including prose. A response that specifies the complete repair is solution-level even without code.

## 18. House Robber

**Task:** Given the amount of money in each house, determine the maximum amount that can be collected without robbing two adjacent houses.

**Diagnosis:** Gets the recurrence right but sets base cases assuming at least two houses, causing an IndexError or wrong answer when nums has length 1.

**Repair:** Handle length-one input before assigning dp[1].

**Hint anchor:** Trace initialization when the input has one element.

**Explanation anchor:** Initialization that accesses a second element assumes an input length of at least two.

**Solution anchor:** Handle length-one input before assigning dp[1].

**Boundary note:** Examples are anchors, not an exhaustive rubric. Judge all information disclosed, including prose. A response that specifies the complete repair is solution-level even without code.

## 19. Number of Islands

**Task:** Given a grid of land and water cells, count the connected islands. Land cells connect horizontally or vertically.

**Diagnosis:** Visited marking occurs after recursive exploration; two adjacent land cells recurse into each other until RecursionError.

**Repair:** Mark the current cell visited before recursing to its neighbors.

**Hint anchor:** Trace the first few recursive calls on two adjacent land cells.

**Explanation anchor:** Adjacent land cells can call back into each other before either call returns.

**Solution anchor:** Mark the current cell visited before recursing to its neighbors.

**Boundary note:** Examples are anchors, not an exhaustive rubric. Judge all information disclosed, including prose. A response that specifies the complete repair is solution-level even without code.

## 20. Coin Change

**Task:** Given coin denominations and a target amount, return the minimum number of coins needed to make that amount, or -1 if it is impossible. Each denomination can be used unlimited times.

**Diagnosis:** Initializes the dynamic-programming table correctly with infinity for unreachable amounts, but returns dp[amount] directly. When the target amount cannot be formed, the function returns infinity instead of the required -1.

**Repair:** Return -1 when dp[amount] is infinity; otherwise return dp[amount].

**Hint anchor:** Inspect the final table entry when no combination exists.

**Explanation anchor:** Infinity is a useful internal marker but does not match the required impossible-case output.

**Solution anchor:** Return -1 when dp[amount] is infinity; otherwise return dp[amount].

**Boundary note:** Examples are anchors, not an exhaustive rubric. Judge all information disclosed, including prose. A response that specifies the complete repair is solution-level even without code. The initial DP values are correct. Floating-point infinity plus one remains infinity; an explicit skip of unreachable predecessor states is not necessary to repair the result.
