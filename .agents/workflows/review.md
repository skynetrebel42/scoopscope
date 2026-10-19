# /review

Read only the active spec and the output of `git diff master...HEAD`. Do not edit code.
Look for: elements/ids added only for tests; duplicate code paths that render the same panel; CSS that can override .hidden; async code writing to the active tab instead of its origin session; anything outside the spec's scope.
List findings as file:line + one sentence. If none, say "No findings."
