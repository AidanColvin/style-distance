# Function flow / FINAL
Function flow for the authorship identification program
```mermaid
flowchart TD
    %% Functions
    main
    test_all_unknowns
    print_all_signatures

    choose_file
    guess_author
    make_known_signatures
    find_closest_signature
    make_signature
    calculate_distance

    save_signatures
    load_signatures
    file_fingerprint
    _signature_task
    _score_task

    average_word_length
    different_to_total
    exactly_once_to_total
    average_sentence_length
    average_sentence_complexity

    get_clean_words
    split_into_sentences
    split_into_phrases
    clean_word
    split_string
    %% Calls
    main --> make_known_signatures
    main --> choose_file
    main --> guess_author

    test_all_unknowns --> make_known_signatures
    test_all_unknowns --> _score_task

    print_all_signatures --> make_known_signatures
    print_all_signatures --> _signature_task
    print_all_signatures --> save_signatures

    make_known_signatures --> load_signatures
    make_known_signatures --> file_fingerprint
    make_known_signatures --> _signature_task
    make_known_signatures --> save_signatures

    guess_author --> make_signature
    guess_author --> find_closest_signature

    _signature_task --> make_signature
    _score_task --> make_signature
    _score_task --> calculate_distance

    find_closest_signature --> calculate_distance

    make_signature --> average_word_length
    make_signature --> different_to_total
    make_signature --> exactly_once_to_total
    make_signature --> average_sentence_length
    make_signature --> average_sentence_complexity

    average_word_length --> get_clean_words
    different_to_total --> get_clean_words
    exactly_once_to_total --> get_clean_words
    get_clean_words --> clean_word

    average_sentence_length --> split_into_sentences
    average_sentence_complexity --> split_into_sentences
    average_sentence_complexity --> split_into_phrases

    split_into_sentences --> split_string
    split_into_phrases --> split_string
```