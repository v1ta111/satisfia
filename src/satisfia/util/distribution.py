#!/usr/bin/env python3

import math
import random
import types

import torch

class _distribution():
	def __init__(self):
		pass

	def _sample_single(self):
		raise NotImplementedError

	def sample(self, n=1):
		return torch.tensor([self._sample_single() for _ in range(n)])

	def median(self, *, precision=64):
		samples = sorted(self.sample(precision))

		left = (precision - 1) // 2
		right = precision // 2

		return samples[left:right+1]

	def E(self, *, precision=64):
		samples = self.sample(precision)
		return sum(samples) / len(samples)

	mean = E

	def var(self, *, precision=64):
		samples = self.sample(precision)
		E = sum(samples) / len(samples)
		return sum((samples - E) ** 2) / (precision - 1) # sample variance

	def stddev(self, *, precision=64):
		return torch.sqrt(self.var(precision))

class categorical(_distribution):
	def __init__(self, categories):
		self._categories = categories.copy()

		self._weight_total = sum([categories[name] for name in categories])
		self._order_sticky = True

	def category_set(self, name, weight):
		if name in self._categories:
			self._weight_total -= self._categories[name]
		self._weight_total += weight
		self._order_sticky = True

		self._categories[name] = weight

	def category_del(self, name):
		if name in self._categories:
			self._weight_total -= self._categories[name]
		self._order_sticky = True

		del self._categories[name]

	def _select(self, chance):
		def priority(name):
			return - self._categories[name]

		if len(self._categories) == 0:
			raise ValueError("No categories")

		if self._order_sticky:
			self._order_sticky = False

			self._order = sorted(self._categories.keys(), key=priority)

		# Iterate from most to the least probable to reduce expected time.
		# Probability is distributed proportionally to weight.
		for name in self._order:
			weight = self._categories[name]
			chance -= weight
			if chance < 0:
				return name

		return self._categories[-1] # this line is reachable due to precision errors

	def _sample_single(self):
		return self._select(random.uniform(0, self._weight_total))

	def median(self):
		# TODO this may return only one of the medians
		return [self._select(self._weight_total / 2.0)]

	def E(self):
		return sum([int(name) * self._categories[name] for name in self._categories]) / self._weight_total

	def var(self):
		E = self.E()
		moment2 = sum([int(name) ** 2 * self._categories[name] for name in self._categories]) / self._weight_total
		return moment2 - E ** 2 # population variance

class uniform(_distribution):
	"""A discrete uniform distribution."""

	def __init__(self, low, high):
		self.low = low
		self.high = high
		self._count = self.high - self.low + 1

	def _sample_single(self):
		return random.randint(self.low, self.high)

	def median(self):
		left = self.low + (self._count - 1) // 2
		right = self.low + (self._count // 2)

		return [left, right] if (right > left) else [left]

	def E(self):
		return (self.low + self.high) / 2

	def var(self):
		return (self._count ** 2 - 1) / 12

def bernoulli(p):
	return categorical({0: 1 - p, 1: p})

def infer(_sample_single):
	d = _distribution()
	d._sample_single = types.MethodType(lambda self: _sample_single(), d)
	return d

import unittest

class TestDistributions(unittest.TestCase):
	def test_bernoulli(self):
		b = bernoulli(0)
		for i in range(100):
			self.assertEqual(b.sample(), 0)

		b = bernoulli(1)
		for i in range(100):
			self.assertEqual(b.sample(), 1)

		b = bernoulli(0.75)
		self.assertEqual(b.median()[0], 1)
		self.assertEqual(b.E(), 0.75)
		self.assertEqual(b.var(), 0.1875)

	def test_categorical(self):
		c = categorical({0: 1, 1: 2, 2: 4})
		self.assertEqual(c.median()[0], 2)
		self.assertAlmostEqual(c.E(), 10 / 7, places=5)

	def test_uniform(self):
		die = uniform(1, 6)
		self.assertEqual(tuple(die.median()), (3, 4))
		self.assertEqual(die.E(), 3.5)
		self.assertAlmostEqual(die.var(), 2.916667, places=5)

		die7 = uniform(1, 7)
		self.assertEqual(tuple(die7.median()), (4,))
		self.assertEqual(die7.E(), 4)

	def test_infer(self):
		values = [1, 3, 5]
		i = infer(lambda: random.choice(values))
		for s in i.sample(100):
			self.assertIn(s, values)

if __name__ == '__main__':
	 unittest.main()