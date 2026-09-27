import {test,after} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,mkdtemp,writeFile,rm,mkdir} from 'node:fs/promises';
import {fileURLToPath,pathToFileURL} from 'node:url';
import ts from 'typescript';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const cache=new URL('../node_modules/.cache/',import.meta.url);await mkdir(cache,{recursive:true});
const directory=await mkdtemp(fileURLToPath(new URL('markdown-',cache)));
const source=await readFile(new URL('../src/MarkdownMessage.tsx',import.meta.url),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const output=directory+'/component.mjs';await writeFile(output,compiled);
const {MarkdownMessage}=await import(pathToFileURL(output).href);
after(()=>rm(directory,{recursive:true,force:true}));
const render=content=>renderToStaticMarkup(React.createElement(MarkdownMessage,{content}));
test('formats Persian text, headings, lists, tables and code with copy buttons',()=>{
 const html=render('# سلام\n\n**Bold**\n\n- item\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n```python\nprint("hello")\n```');
 for(const expected of ['<h1>سلام</h1>','<strong>Bold</strong>','<li>item</li>','<table>','<pre>','Copy code','Copy response'])assert.ok(html.includes(expected),expected);
});
test('does not execute raw HTML or expose unsafe links and remote images',()=>{
 const html=render('<script>alert(1)</script>\n\n[bad](javascript:alert%281%29)\n\n![tracking](https://example.com/pixel.png)\n\n[safe](https://example.com)');
 assert.ok(!html.includes('<script'));assert.ok(!html.includes('href="javascript:'));assert.ok(!html.includes('<img'));
 assert.ok(html.includes('href="https://example.com"'));assert.ok(html.includes('noopener noreferrer'));
});
test('renders HTML inside fenced code as inert text',()=>{
 const html=render('```html\n<script>alert(1)</script>\n```');
 assert.ok(html.includes('&lt;script&gt;'));assert.ok(!html.includes('<script>'));
});
