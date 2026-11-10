# Style Guide

The canonical authoring rules for this repository, which every contributor and every agent that writes or edits a page under the docs folder is expected to read before they start, are set out below in full.

Each page should open with a paragraph that explains to the reader what the page is about, who it was written for, and what they will be able to do once they have read it from the start to the end.

When a procedure is described, the steps that the reader is expected to follow should be written in the order in which they are carried out, with each step stated in a sentence of its own.

Sentences that run on for a long time, joining several ideas with commas and conjunctions, are harder for a new engineer to follow than short sentences that each state a single fact about the system.

Terms that are defined in the glossary should be used consistently on every page, so that the reader never has to wonder whether two different words that appear in two places mean the same thing.

Diagrams should be drawn in Mermaid and placed close to the text that they illustrate, and each one should be introduced by a sentence that tells the reader what the diagram shows and why it matters.

Code, commands, file names and configuration keys should always be written in code spans, because that makes it clear to the reader which parts of the sentence are literal values they can copy.

Links to other pages should use the title of the page as their text rather than a phrase such as "click here", because the reader should be able to tell where a link goes before following it.

A page that describes a decision should state the context, the options that were considered, the option that was chosen and the reason it was chosen, and it should link to the record of the decision.

Pages are reviewed in the same pull request as the code that they describe, and a reviewer who finds that a page no longer matches the code should ask for the page to be updated before approving.

Short pages are easier to keep accurate.
