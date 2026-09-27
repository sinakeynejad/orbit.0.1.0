import {useEffect, useRef, useState} from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type {Components} from 'react-markdown';

export function CopyButton({text,label='Copy response'}:{text:string;label?:string}) {
 const [state,setState]=useState('');
 const timer=useRef<ReturnType<typeof setTimeout>|null>(null);
 useEffect(()=>()=>{if(timer.current)clearTimeout(timer.current);},[]);
 async function copy(){
  try{await navigator.clipboard.writeText(text);setState('Copied');}
  catch{setState('Copy failed — select and copy manually');}
  if(timer.current)clearTimeout(timer.current);
  timer.current=setTimeout(()=>setState(''),3000);
 }
 return <span className="copy-control"><button type="button" onClick={()=>void copy()} aria-label={label}>{label}</button><span role="status">{state}</span></span>;
}
const components:Components={
 pre({children,node}){
  const code=node?.children.find(child=>child.type==='element'&&child.tagName==='code');
  const text=code?.type==='element'?code.children.map(child=>child.type==='text'?child.value:'').join(''):'';
  return <div className="code-block" dir="ltr"><div className="code-toolbar"><span>Code</span><CopyButton text={text} label="Copy code"/></div><pre>{children}</pre></div>;
 },
 table({children}){return <div className="table-scroll"><table>{children}</table></div>;},
 a({href,children}){return href?<a href={href} target="_blank" rel="noopener noreferrer">{children}</a>:<span>{children}</span>;},
 img({alt}){return <span>[Image: {alt||'image'}]</span>;},
};
export function MarkdownMessage({content}:{content:string}){
 return <><div className="message-text markdown" dir="auto"><Markdown remarkPlugins={[remarkGfm]} skipHtml components={components} urlTransform={url=>/^https?:\/\//i.test(url)?url:''}>{content}</Markdown></div><CopyButton text={content}/></>;
}
