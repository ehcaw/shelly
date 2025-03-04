class Solution:
    def twoSum(self, nums, target):
        seen_numbers = {}

        for i in range(len(nums))
            current = nums[i]
            complement = target - current

            if seen_numbers[complement]:
                return [seen_numbers[complement], i]

            seen_numbers = {current: i}
