import math
import random


def generate_gaussian_dict():

    values = list(range(500, 1000, 25))

    mean = 750
    std_dev = 168

    weights = [math.exp(-((x - mean) ** 2) / (2 * std_dev ** 2))
               for x in values]

    chosen_number = random.choices(values, weights=weights, k=1)[0]

    return {
        "chunk_size": chosen_number,
        "overlap_size": chosen_number * 0.20
    }
