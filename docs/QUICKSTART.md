# Quickstart: Fine-tune your first model

This guide walks you through installing llmtuner and fine-tuning your first model. No coding required.

## What you'll need

- A Mac with Apple Silicon (M1, M2, M3, M4)
- At least 10GB of free disk space
- An internet connection (for downloading models and dependencies)

That's it. No Python knowledge, no terminal experience, no cloud accounts.

## Step 1: Install llmtuner

Open Terminal (you can find it in Applications → Utilities, or search with Spotlight).

Paste this command and press Enter:

```bash
curl -fsSL https://raw.githubusercontent.com/lecharles/llm-fine-tuner-agent-tester/main/install.sh | bash
```

This will:
- Check that you have Python 3.12+ (if not, it will tell you how to install it)
- Download the app to `~/.llmtuner`
- Set up everything it needs
- **Prompt you for API keys** (Anthropic for Q&A generation, OpenAI for compare chat)
- Create the `llmtuner` command

When it's done, you'll see a green checkmark and a message like "Installation complete!"

**About API keys:**
- The installer will ask for your Anthropic and OpenAI API keys
- These unlock features like auto-generating Q&A pairs and comparing against hosted models
- If you don't have them yet, press Enter to skip — you can add them later
- To get an Anthropic key: https://console.anthropic.com/
- To get an OpenAI key: https://platform.openai.com/api-keys

**If it says Python is missing or too old:**
- Install Python from https://www.python.org/downloads/
- Restart Terminal and try the install command again

**If it says `~/.local/bin is not on your PATH`:**
- Open `~/.zshrc` (or `~/.bashrc` if you use bash) in a text editor
- Add this line at the end: `export PATH="$HOME/.local/bin:$PATH"`
- Save and restart Terminal

## Step 2: Start the app

In Terminal, run:

```bash
llmtuner up
```

This will:
- Run a few checks (Apple Silicon, disk space, etc.)
- Set up the database
- Start the app on http://localhost:8000
- Open your browser automatically

You should see the llmtuner login screen.

**If the browser doesn't open automatically:**
- Open your browser manually and go to http://localhost:8000

## Step 3: Create your account

Since you're running locally, the app is in "local mode" — no signup needed. You're automatically logged in as the local user.

**If you see a login screen:**
- This means local mode isn't active. Run `llmtuner up` again, or check that `LOCAL_MODE=true` is set in your environment.

## Step 4: Create a dataset

A dataset is a collection of question-answer pairs that teach the model what you want it to learn.

1. Click **"Datasets"** in the sidebar
2. Click **"New Dataset"**
3. Fill in:
   - **Name**: something descriptive, like "Geography Expert" or "Customer Support Bot"
   - **Description**: what this dataset is for
   - **Source**: choose "Manual" for now
4. Click **"Create"**

## Step 5: Add question-answer pairs

Now you'll teach the model by giving it examples.

1. Click on your dataset to open it
2. Click **"Add QA Pair"**
3. Fill in:
   - **Question**: e.g. "What is the capital of France?"
   - **Answer**: e.g. "The capital of France is Paris."
4. Click **"Save"**
5. Repeat for 10-20 pairs to start

**Tips for good QA pairs:**
- Be specific and clear
- Cover different variations of the same topic
- Include edge cases if relevant
- Aim for at least 20-50 pairs for a useful model

**Want to generate pairs automatically?**
- Click **"Generate from Prompt"**
- Describe your use case in plain English, e.g. "A geography expert that answers questions about world capitals and landmarks"
- The app will generate pairs for you
- Review and edit them as needed

## Step 6: Train your model

Now the magic happens.

1. Click **"Train"** in the sidebar
2. Select your dataset
3. Choose a base model:
   - **Llama 3.2 1B**: faster, uses less memory, good for testing
   - **Llama 3.2 3B**: better quality, needs more memory
4. Set the number of training iterations:
   - **10-20**: plumbing smoke test only (proves the pipeline, no real quality)
   - **200-400**: recommended for a usable model
   - **500+**: deep training, only after 200-400 gives good results
5. Click **"Start Training"**

The training will run in the background. You'll see a progress indicator.

**How long does it take?**
- 1B model, 50 iterations: ~2-5 minutes
- 3B model, 500 iterations: ~30-60 minutes
- Depends on your Mac and dataset size

**Can I keep working while it trains?**
Yes. The training runs in the background. You can browse the app, add more data, or just wait.

## Step 7: Test your model

Once training is complete, you can compare your fine-tuned model against others.

1. Click **"Compare"** in the sidebar
All four columns answer in under 150 words, so comparisons stay fair and readable.

2. Your fine-tuned model is already selected
3. Choose comparison models:
   - The base model (untuned)
   - An OpenAI model (e.g. GPT-4)
   - An Anthropic model (e.g. Claude)
4. Type a question in the chat box
5. See how all four models respond side-by-side

**What to look for:**
- Does your fine-tuned model answer in the style you taught it?
- Is it more accurate on your specific topic than the base model?
- How does it compare to the big hosted models?

## Step 8: Export your model (optional)

Want to use your model outside llmtuner?

1. Click **"Models"** in the sidebar
2. Find your fine-tuned model
3. Click **"Export"**
4. Choose GGUF format (works with Ollama, llama.cpp, etc.)
5. Save the file

You can now load this GGUF file in other tools that support the format.

## Troubleshooting

**"Not enough disk space"**
- Free up at least 10GB
- Models and training artifacts take space
- You can delete old training runs in `~/.llmtuner/training_runs/`

**Training fails with "Out of memory"**
- Switch to the 1B model
- Reduce the number of iterations
- Close other apps to free up memory

**App won't start**
- Run `llmtuner doctor` to check prerequisites
- Make sure you're on Apple Silicon (M1/M2/M3/M4)
- Check that port 8000 isn't in use: `lsof -i :8000`

**Browser shows a blank page**
- Hard refresh: Cmd+Shift+R
- Check the browser console for errors (F12 → Console)
- Try a different browser

**Need help?**
- Open an issue on GitHub: https://github.com/lecharles/llm-fine-tuner-agent-tester/issues
- Include the output of `llmtuner doctor` and any error messages

## What's next?

- **More datasets**: create datasets for different use cases
- **Better training**: experiment with more iterations, larger models
- **Advanced mode**: (coming soon) expose hyperparameters like learning rate, batch size
- **Share your models**: (coming soon) make datasets and models public

## Uninstalling

To remove llmtuner:

```bash
rm -rf ~/.llmtuner
rm ~/.local/bin/llmtuner
```

That's it. No traces left behind.
