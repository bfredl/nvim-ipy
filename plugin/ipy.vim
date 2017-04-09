command! -nargs=* IPython :call IPyConnect(<f-args>)
command! -nargs=* IPython2 :call IPyConnect("--kernel", "python2")
command! -nargs=* IJulia :call IPyConnect("--kernel", "julia-0.4")

nnoremap <Plug>(IPy-Run) :call IPyRun(getline('.'))<cr>
vnoremap <Plug>(IPy-Run) :<c-u>call IPyRun(<SID>get_visual_selection())<cr>
noremap <Plug>(IPyRunCell) :call IPyRunCell()<cr>
inoremap <Plug>(IPy-Complete) <c-o>:<c-u>call IPyComplete()<cr>
noremap <Plug>(IPy-WordObjInfo) :call IPyObjInfo(<SID>get_current_word(), 0)<cr>
noremap <Plug>(IPy-Interrupt) :call IPyInterrupt()<cr>
noremap <Plug>(IPy-Terminate) :call IPyTerminate()<cr>

" make this overrideable
hi IPyIn ctermfg=green cterm=bold guifg=LimeGreen gui=bold
hi IPyOut ctermfg=red cterm=bold guifg=red gui=bold
hi IPyBold cterm=bold gui=bold
let s:colors = ["Black", "Red", "Green", "DarkYellow", "Blue", "DarkMagenta", "#00bbdd", "LightGray",
             \  "Gray", "#ff4444", "LimeGreen", "Yellow", "LightBlue", "Magenta", "Cyan", "White"]
for i in range(0,15)
    execute "hi IPyFg".i." ctermfg=".i." guifg=".s:colors[i]
endfor

function! s:get_current_word()
    let isk_save = &isk
    let &isk = '@,48-57,_,192-255,.'
    let word = expand("<cword>")
    let &isk = isk_save
    return word
endfunction

" thanks to @xolox on stackoverflow
function! s:get_visual_selection()
    let [lnum1, col1] = getpos("'<")[1:2]
    let [lnum2, col2] = getpos("'>")[1:2]
    let lines = getline(lnum1, lnum2)
    let lines[-1] = lines[-1][: col2 - (&selection == 'inclusive' ? 1 : 2)]
    let lines[0] = lines[0][col1 - 1:]
    return join(lines, "\n")
endfunction

if !exists('g:nvim_ipy_perform_mappings')
    let g:nvim_ipy_perform_mappings = 1
endif

let g:ipy_status = ""

if g:nvim_ipy_perform_mappings
    map <silent> <F5>           <Plug>(IPy-Run)
    map <leader>c <Plug>(IPy-Run-Cell)
    imap <silent> <C-F> <Plug>(IPy-Complete)
    map <silent> <F8> <Plug>(IPy-Interrupt)
    map <silent> <leader>? <Plug>(IPy-WordObjInfo)
    "set titlestring=%t%(\ %M%)%(\ (%{expand(\"%:p:h\")})%)%(\ %a%)%(\ -\ %{g:ipy_status}%)
endif


