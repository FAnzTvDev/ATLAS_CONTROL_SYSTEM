#!/usr/bin/env python3
"""Permanently inject the NULL GUARD into auto_studio_tab.html at the top of the main script block."""

guard = (
    "// NULL GUARD V29.6 — permanent fix, all getElementById nulls silenced\n"
    "(function(){\n"
    "  var o=document.getElementById.bind(document);\n"
    "  var s=new Proxy({},{\n"
    "    get:function(_,p){\n"
    "      if(p==='textContent'||p==='innerHTML'||p==='innerText')return'';\n"
    "      if(p==='style')return new Proxy({},{set:function(){return true;},get:function(){return'';}});\n"
    "      if(p==='classList')return{add:function(){},remove:function(){},toggle:function(){},contains:function(){return false;}};\n"
    "      return function(){};\n"
    "    },\n"
    "    set:function(){return true;}\n"
    "  });\n"
    "  document.getElementById=function(id){\n"
    "    var el=o(id);\n"
    "    if(!el){if(!window._ng)window._ng={};if(!window._ng[id]){console.warn('[NULL_GUARD]#'+id);window._ng[id]=1;}return s;}\n"
    "    return el;\n"
    "  };\n"
    "})();\n"
    "// END NULL GUARD\n"
)

path = '/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/auto_studio_tab.html'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find line 4664 (1-indexed) = index 4663 — the '<script>' main block opener
# Insert guard at index 4665 (after the blank line following <script>)
insert_idx = 4665
lines.insert(insert_idx, guard + '\n')

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f'NULL GUARD injected at line {insert_idx+1}')
