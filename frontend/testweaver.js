{
  const dialog = document.getElementById("testweaverModal");
  const setup = document.getElementById("testweaverSetup");
  const source = document.getElementById("testweaverSource");
  const count = document.getElementById("testweaverCount");
  const generate = document.getElementById("generateTestweaver");
  const answersForm = document.getElementById("testweaverAnswers");
  const questionsList = document.getElementById("testweaverQuestions");
  const submit = document.getElementById("submitTestweaver");
  const status = document.getElementById("testweaverStatus");
  const empty = document.getElementById("testweaverEmpty");
  const loading = document.getElementById("testweaverLoading");
  const scoreCard = document.getElementById("testweaverScore");
  const scroll = document.getElementById("testweaverScroll");
  let questions = [];
  let pairs = [];
  let mode = "objective";
  let busy = false;
  let graded = false;
  let savedObjectiveCount = 5;

  document.addEventListener("notebook-sources-updated", (event) => {
    const previous = source.value;
    source.replaceChildren();
    for (const item of event.detail) {
      const option = document.createElement("option");
      option.value = item.document_id;
      option.textContent = item.title;
      source.appendChild(option);
    }
    if (event.detail.some((item) => item.document_id === previous)) source.value = previous;
    if (!event.detail.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "No sources yet";
      source.appendChild(option);
      if (!questions.length) status.textContent = "Add a document, website, or video to this notebook first.";
    }
    answersForm.dispatchEvent(new Event("input"));
  });

  document.getElementById("testweaverButton").addEventListener("click", () => {
    document.dispatchEvent(new CustomEvent("notebook-sources-updated", { detail: mindMapSources }));
    dialog.showModal();
    document.getElementById("closeTestweaver").focus();
  });

  document.getElementById("closeTestweaver").addEventListener("click", () => {
    if (dialog.classList.contains("tw-closing")) return;
    dialog.classList.add("tw-closing");
    setTimeout(() => {
      dialog.close();
      dialog.classList.remove("tw-closing");
      document.getElementById("testweaverButton").focus();
    }, window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 180);
  });
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    document.getElementById("closeTestweaver").click();
  });
  dialog.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (button && !button.disabled) {
      button.classList.remove("tw-pressed");
      void button.offsetWidth;
      button.classList.add("tw-pressed");
    }
    if (event.target !== dialog) return;
    const bounds = dialog.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) {
      document.getElementById("closeTestweaver").click();
    }
  });
  dialog.addEventListener("animationend", (event) => {
    if (event.animationName === "tw-press") event.target.classList.remove("tw-pressed");
  });

  setup.addEventListener("change", (event) => {
    if (event.target.name !== "testweaverMode") return;
    const subjective = event.target.value === "subjective";
    if (subjective) {
      savedObjectiveCount = Number(count.value) || 5;
      count.value = Math.min(3, Math.max(1, savedObjectiveCount));
    } else {
      count.value = savedObjectiveCount;
    }
    count.max = subjective ? "3" : "10";
    document.getElementById("testweaverCountHint").textContent = subjective ? "Up to 3 extended questions." : "Choose between 1 and 10.";
    document.getElementById("testweaverModeDescription").textContent = subjective ? "Explain your thinking. Get feedback on the points you missed." : "You will be given four choices and one of them will be correct.";
  });

  answersForm.addEventListener("input", () => {
    let answered = 0;
    for (let index = 0; index < questions.length; index++) {
      if (mode === "objective") {
        if (answersForm.querySelector(`input[name="tw-answer-${index}"]:checked`)) answered++;
      } else if (document.getElementById(`tw-answer-${index}`)?.value.trim()) {
        answered++;
      }
    }
    document.getElementById("testweaverProgressText").textContent = graded ? `${questions.length} questions reviewed` : `${answered} of ${questions.length} answered`;
    const progress = questions.length ? Math.round(answered / questions.length * 100) : 0;
    document.getElementById("testweaverProgress").style.width = `${progress}%`;
    document.getElementById("testweaverProgress").parentElement.setAttribute("aria-valuenow", String(progress));
    submit.disabled = busy || graded || !questions.length || answered !== questions.length;
    generate.disabled = busy || !source.value;
    source.disabled = busy || !source.value;
    count.disabled = busy;
    for (const input of setup.querySelectorAll('input[name="testweaverMode"]')) input.disabled = busy;
    for (const field of answersForm.querySelectorAll("fieldset")) field.disabled = busy || graded;
  });

  setup.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy || !notebookId || !source.value || !setup.reportValidity()) return;
    const requestedMode = setup.querySelector('input[name="testweaverMode"]:checked').value;
    const requestedCount = Number(count.value);
    const documentId = source.value;
    const sourceTitle = source.selectedOptions[0].textContent;
    busy = true;
    status.classList.remove("tw-error");
    status.textContent = "Building a test from your selected source.";
    loading.hidden = false;
    empty.hidden = true;
    answersForm.hidden = true;
    generate.textContent = "Generating...";
    answersForm.dispatchEvent(new Event("input"));
    try {
      const parameters = new URLSearchParams({ document_id: documentId, notebook_id: notebookId, number_of_questions: String(requestedCount) });
      const response = await apiRequest(`/testweaver/${requestedMode}/generate?${parameters}`, { method: "POST" });
      const generated = Array.isArray(response) ? response : requestedMode === "objective" ? response.mcq_questions : response.question_answer_pairs;
      if (!Array.isArray(generated) || generated.length !== requestedCount) throw new Error("The generated test has an unexpected question count. Try generating again.");
      const generatedQuestions = requestedMode === "objective" ? generated : generated.map((pair) => pair[0]);
      for (let index = 0; index < generatedQuestions.length; index++) {
        const question = generatedQuestions[index];
        if (!question || typeof question.question !== "string" || !["easy", "medium", "hard"].includes(question.difficulty)) throw new Error("A generated question has an invalid format. Try again.");
        if (requestedMode === "objective" && (!Array.isArray(question.options) || question.options.length !== 4 || !question.options.every((option) => typeof option === "string") || !question.options.includes(question.correct_option))) throw new Error("A multiple-choice question has an invalid answer key. Try again.");
        if (requestedMode === "subjective" && typeof generated[index][1] !== "string") throw new Error("A question is missing its expected answer. Try again.");
      }
      if (!mindMapSources.some((item) => item.document_id === documentId)) throw new Error("This source was removed while the test was being generated. Choose another source.");
      questions = generatedQuestions;
      pairs = requestedMode === "subjective" ? generated : [];
      mode = requestedMode;
      graded = false;
      scoreCard.hidden = true;
      questionsList.replaceChildren();
      for (let index = 0; index < questions.length; index++) {
        const question = questions[index];
        const card = document.createElement("article");
        card.className = "tw-question";
        card.style.setProperty("--tw-delay", `${index * 90}ms`);
        const top = document.createElement("div");
        top.className = "tw-question-top";
        const number = document.createElement("span");
        number.className = "tw-question-number";
        number.textContent = `Question ${String(index + 1).padStart(2, "0")}`;
        const badge = document.createElement("span");
        badge.className = `tw-difficulty ${question.difficulty}`;
        badge.textContent = question.difficulty[0].toUpperCase() + question.difficulty.slice(1);
        top.append(number, badge);
        const title = document.createElement("h3");
        title.id = `tw-question-${index}`;
        renderFormattedText(title, question.question);
        const field = document.createElement("fieldset");
        field.className = "tw-answer-field";
        field.setAttribute("aria-labelledby", title.id);
        if (mode === "objective") {
          field.classList.add("tw-options");
          for (let optionIndex = 0; optionIndex < question.options.length; optionIndex++) {
            const option = document.createElement("label");
            option.className = "tw-option";
            const input = document.createElement("input");
            input.type = "radio";
            input.name = `tw-answer-${index}`;
            input.value = question.options[optionIndex];
            input.required = true;
            const letter = document.createElement("span");
            letter.className = "tw-option-letter";
            letter.textContent = "ABCD"[optionIndex];
            letter.setAttribute("aria-hidden", "true");
            const text = document.createElement("span");
            text.className = "tw-option-text";
            text.textContent = question.options[optionIndex];
            const note = document.createElement("span");
            note.className = "tw-option-note";
            note.hidden = true;
            option.append(input, letter, text, note);
            field.appendChild(option);
          }
        } else {
          const input = document.createElement("textarea");
          input.className = "tw-written-answer";
          input.id = `tw-answer-${index}`;
          input.placeholder = "Explain it in your own words...";
          input.required = true;
          input.setAttribute("aria-labelledby", title.id);
          field.appendChild(input);
        }
        card.append(top, title, field);
        questionsList.appendChild(card);
      }
      answersForm.hidden = false;
      document.getElementById("testweaverTestTitle").textContent = `${mode === "objective" ? "Objective" : "Subjective"} practice / ${sourceTitle}`;
      status.textContent = "Take your time. Answer every question, then check your understanding.";
      scroll.scrollTop = 0;
      submit.textContent = "Check answers";
    } catch (error) {
      status.textContent = `${error.message} You can try again.`;
      status.classList.add("tw-error");
      answersForm.hidden = !questions.length;
      empty.hidden = Boolean(questions.length);
    } finally {
      busy = false;
      loading.hidden = true;
      generate.textContent = questions.length ? "Generate new test" : "Generate test";
      answersForm.dispatchEvent(new Event("input"));
    }
  });

  answersForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy || graded || submit.disabled || !answersForm.reportValidity()) return;
    const answers = questions.map((_, index) => mode === "objective" ? answersForm.querySelector(`input[name="tw-answer-${index}"]:checked`).value : document.getElementById(`tw-answer-${index}`).value);
    busy = true;
    status.classList.remove("tw-error");
    status.textContent = mode === "subjective" ? "Checking your reasoning against the expected answers. This can take a moment." : "Checking your choices...";
    submit.textContent = "Checking...";
    answersForm.setAttribute("aria-busy", "true");
    answersForm.dispatchEvent(new Event("input"));
    try {
      const body = mode === "objective" ? { question_list: questions, provided_answers_list: answers } : { pairs_list: pairs, answer_list: answers };
      const response = await apiRequest(`/testweaver/${mode}/submit`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const results = Array.isArray(response) ? response : response.results;
      if (!Array.isArray(results) || results.length !== questions.length || results.some((result) => !result || !Number.isFinite(result.score) || result.score < 0 || result.score > 10 || !["correct", "partially_correct", "incorrect"].includes(result.correctness) || (result.points_to_improve != null && (!Array.isArray(result.points_to_improve) || !result.points_to_improve.every((point) => typeof point === "string"))))) throw new Error("The feedback has an unexpected format. Try checking again.");
      let total = 0;
      let correct = 0;
      for (let index = 0; index < results.length; index++) {
        const result = results[index];
        const question = questions[index];
        const card = questionsList.children[index];
        total += result.score;
        if (result.correctness === "correct") correct++;
        if (mode === "objective") {
          for (const option of card.querySelectorAll(".tw-option")) {
            const input = option.querySelector("input");
            if (input.value === question.correct_option) {
              option.classList.add("tw-correct");
              const note = option.querySelector(".tw-option-note");
              note.textContent = "Correct answer";
              note.hidden = false;
            } else if (input.checked) {
              option.classList.add("tw-wrong");
            }
          }
        }
        const feedback = document.createElement("section");
        feedback.className = "tw-feedback";
        feedback.setAttribute("aria-label", `Feedback for question ${index + 1}`);
        const heading = document.createElement("div");
        heading.className = `tw-feedback-heading ${result.correctness}`;
        const verdict = document.createElement("strong");
        verdict.textContent = result.correctness === "correct" ? "Correct" : result.correctness === "partially_correct" ? "Partially correct" : "Room to improve";
        const score = document.createElement("span");
        score.textContent = `${result.score} / 10`;
        heading.append(verdict, score);
        feedback.appendChild(heading);
        if (mode === "objective") {
          const explanation = document.createElement("div");
          renderFormattedText(explanation, result.mcq_explanation || question.explanation || "");
          feedback.appendChild(explanation);
        } else {
          if (result.points_to_improve?.length) {
            const label = document.createElement("p");
            label.textContent = "To strengthen your answer:";
            const list = document.createElement("ul");
            for (const point of result.points_to_improve) {
              const item = document.createElement("li");
              item.textContent = point;
              list.appendChild(item);
            }
            feedback.append(label, list);
          } else {
            const note = document.createElement("p");
            note.textContent = result.correctness === "correct" ? "You covered the essential points." : "Review the expected answer to see how to develop your response.";
            feedback.appendChild(note);
          }
          const details = document.createElement("details");
          const summary = document.createElement("summary");
          summary.textContent = "Explore the expected answer";
          const expected = document.createElement("div");
          renderFormattedText(expected, pairs[index][1]);
          details.append(summary, expected);
          feedback.appendChild(details);
        }
        card.appendChild(feedback);
      }
      document.getElementById("testweaverScoreValue").textContent = (total / questions.length).toFixed(1).replace(/\.0$/, "");
      document.getElementById("testweaverScoreTitle").textContent = correct === questions.length ? "Nicely understood." : "Needs improvement.";
      document.getElementById("testweaverScoreDescription").textContent = `${correct} of ${questions.length} fully correct. Review the feedback below, then try a fresh test.`;
      scoreCard.hidden = false;
      graded = true;
      submit.textContent = "Reviewed";
      status.textContent = "Your feedback is ready.";
      if (window.matchMedia("(max-width: 720px)").matches) scoreCard.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block: "start" });
      else scroll.scrollTo({ top: 0, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
      scoreCard.focus({ preventScroll: true });
    } catch (error) {
      status.textContent = `${error.message} Your answers are still here. Try Check answers again.`;
      status.classList.add("tw-error");
      submit.textContent = "Check answers";
    } finally {
      busy = false;
      answersForm.setAttribute("aria-busy", "false");
      answersForm.dispatchEvent(new Event("input"));
    }
  });
}
