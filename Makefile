TEXTS_DIR := text

.PHONY: run choose signatures clean

# guesses the author of every file in unlabeled/, prints each result
run:
	python3 main.py $(TEXTS_DIR) --test-all

# interactive mode: pick one unlabeled file, guess its author
choose:
	python3 main.py $(TEXTS_DIR)

# print + save every known and unknown signature to signatures.json
signatures:
	python3 main.py $(TEXTS_DIR) --print-signatures

# delete cached signatures so the next run recomputes from scratch
clean:
	rm -f $(TEXTS_DIR)/labeled/known_signatures.json signatures.json