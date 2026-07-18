from vllm import LLM, SamplingParams


def main() -> None:
	llm = LLM(model="facebook/opt-125m", gpu_memory_utilization=0.15)
	prompts = [
		"count 1 to 10",
		"write a short haiku about coding",
		"explain recursion in one sentence",
	]
	sampling_params = SamplingParams(max_tokens=40, n=1)
	outputs = llm.generate(prompts, sampling_params)

	for i, request_output in enumerate(outputs):
		print(f"\n{'=' * 70}")
		print(f"Prompt #{i + 1}: {prompts[i]}")
		print("Full request output object:")
		print(request_output)

		for j, completion in enumerate(request_output.outputs):
			print(f"\nCompletion #{j + 1} text:")
			print(completion.text)
			print(f"finish_reason={completion.finish_reason}")
			print(f"token_count={len(completion.token_ids)}")


if __name__ == "__main__":
	main()
