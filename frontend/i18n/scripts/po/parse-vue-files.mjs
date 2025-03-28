// This implementation is loosely copied from vue-i18n-extract
// https://github.com/pixari/vue-i18n-extract
import { readFileSync } from "fs"
import { join } from "path"

import { glob } from "glob"

import { srcDir } from "../paths.mjs"

/**
 * Parses all vue files found in the glob paths, and returns an
 * array of objects with i18n path, line number, and vue file path.
 * {
    path: 'browsePage.aria.close',
    line: 13,
    file: '/components/AppModal.vue'
  },
 * from the BASE_PATH (`openverse/frontend/src`)
 * @return {Array<Object>}
 */
export const getParsedVueFiles = () => {
  // Look for .vue and .js files in the src directory
  const pattern = join(srcDir, "**/*.?(js|vue)")

  const targetFiles = glob.sync(pattern)
  if (targetFiles.length === 0) {
    throw new Error("vueFiles glob has no files.")
  }
  const filesList = targetFiles.map((f) => {
    const fileName = f.replace(srcDir, "src")
    return {
      fileName,
      path: f,
      content: readFileSync(f, "utf8"),
    }
  })
  return extractI18nItemsFromVueFiles(filesList)
}

function* getMatches(file, regExp, captureGroup = 1) {
  while (true) {
    const match = regExp.exec(file.content)

    if (match === null) {
      break
    }

    const line =
      (file.content.substring(0, match.index).match(/\n/g) || []).length + 1
    yield {
      path: match[captureGroup],
      line,
      file: file.fileName,
    }
  }
}

/**
 * Extracts translation keys from methods such as `$t` and `$tc`.
 *
 * - **regexp pattern**: (?:[$ .]t)\(
 *
 *   **description**: Matches the sequence t( optionally with either “$”, “.” or “ ” in front of it.
 *
 * - **regexp pattern**: (["'`])
 *
 *   **description**: 1. capturing group. Matches either “"”, “'”, or “`”.
 *
 * - **regexp pattern**: ((?:[^\\]|\\.)*?)
 *
 *   **description**: 2. capturing group. Matches anything except a backslash
 *   *or* matches any backslash followed by any character (e.g. “\"”, “\`”, “\t”, etc.)
 *
 * - **regexp pattern**: \1
 *
 *   **description**: matches whatever was matched by capturing group 1 (e.g. the starting string character)
 *
 * @param file a file object
 * @returns a list of translation keys found in `file`.
 */

function extractMethodMatches(file) {
  const methodRegExp = /[$ .]t\(\s*?(["'`])((?:[^\\]|\\.)*?)\1/g
  return [...getMatches(file, methodRegExp, 2)]
}

function extractComponentMatches(file) {
  const componentRegExp = /<i18n-t(?:.|\n)*?[^:]path=(["'])(.*?)\1/gi
  return [...getMatches(file, componentRegExp, 2)]
}

function extractI18nItemsFromVueFiles(sourceFiles) {
  return sourceFiles.reduce((accumulator, file) => {
    const methodMatches = extractMethodMatches(file)
    const componentMatches = extractComponentMatches(file)
    return [...accumulator, ...methodMatches, ...componentMatches]
  }, [])
}
