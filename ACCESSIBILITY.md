# Accessibility review

This app is designed to support keyboard use, a plain-text editor, reduced motion, and Windows high-contrast settings. The review uses WCAG 2.2 AA as a target: https://www.w3.org/TR/WCAG22/.

## Review coverage

- Inspected the welcome screen, lesson navigation, lesson content, code and input editors, output, hints, checks, saved state, progress reset, and quit flow.
- Tested keyboard navigation into and out of the highlighted editor, focus after opening a lesson and checking an answer, and the plain-text editor's editing, checking, switching, and saved-work restoration.
- Checked the accessibility tree for labels, lesson status, editor, output, and focus; checked a 320-CSS-pixel-wide viewport for main-content reflow.
- Reviewed contrast of identified low-contrast text and button colors, visible focus styling, the reduced-motion preference, and forced-colors styles. These checks are not a comprehensive contrast measurement of every dynamic state.
- Follow-up review: used an isolated test copy with line height 1.5, paragraph spacing 2em, letter spacing 0.12em, and word spacing 0.16em. At a 320-CSS-pixel viewport, checked all eight lessons for main-content horizontal overflow and clipped lesson titles, buttons, labels, headings, and paragraphs. Code examples and the lesson selector retain their own scroll areas.
- Checked rendered interactive target dimensions on the sampled lesson screen at that width; all enabled buttons, links, and the editor-mode checkbox measured at least 24 by 24 CSS pixels. This is a sampled measurement, not a complete target-spacing audit.
- Ran axe-core's WCAG A/AA rules on the welcome screen and sampled lesson workspace and feedback states. The identified visible-label mismatch and editor-comment contrast failure were repaired; later sampled scans reported no violations, but axe flagged contrast and label checks as requiring manual review. Automated results cannot establish conformance.

## Follow-up before claiming conformance

The review is not a WCAG conformance certification. Complete an independent end-to-end assessment with assistive-technology users, including NVDA and Narrator with supported browsers, and verify live-region announcements, Windows forced-colors themes, actual browser zoom, pointer target spacing, and contrast in every state. Narrator is installed on the review computer, but its spoken output was not independently verified; NVDA was not found. The 320-pixel and text-spacing checks used a browser viewport override and a test-only stylesheet, not actual browser zoom or a user's accessibility extension. Test across all lessons and supported browser versions. The highlighted editor is a third-party component; the plain-text editor provides a simpler alternative but also requires assistive-technology testing.

## Keyboard notes

- Use the first link to skip to the lesson content. Lesson buttons open the lesson and move focus to its heading.
- Tab leaves either editor. In the highlighted editor, Ctrl+] indents and Ctrl+Enter runs code. In the plain-text editor, enter spaces to indent and use Ctrl+Enter to run.
- The program-output area can receive focus so keyboard users can scroll long output. The plain-text option is remembered in the browser on that computer.
