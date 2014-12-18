command! -nargs=* IPython :call IPyConnect(<f-args>)
command! -nargs=* IPython3 :call IPyConnect("--kernel", "python3")
command! -nargs=* IJulia :call IPyConnect("--profile", "julia")

nnoremap <Plug>(IPy-Run) :call IPyRun(getline('.'))<cr>
vnoremap <Plug>(IPy-Run) :<c-u>call IPyRun(<SID>get_visual_selection())<cr>
inoremap <Plug>(IPy-Complete) <c-o>:<c-u>call IPyComplete()<cr>
noremap <Plug>(IPy-Interrupt) :call IPyInterrupt()<cr>
noremap <Plug>(IPy-Terminate) :call IPyTerminate()<cr>

" make this overrideable
hi IpyIn ctermfg=green cterm=bold
hi IpyOut ctermfg=red cterm=bold

function! IPyWordObjinfo()
    let isk_save = &isk
    let &isk = '@,48-57,_,192-255,.'
    let word = expand("<cword>")
    let &isk = isk_save
    call IPyObjInfo(word, 0)
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
    imap <silent> <C-Space> <Plug>(IPy-Complete)
    map <silent> <F8> <Plug>(IPy-Interrupt)
    map <silent> <Leader>d :call IPyWordObjinfo()
    "set titlestring=%t%(\ %M%)%(\ (%{expand(\"%:p:h\")})%)%(\ %a%)%(\ -\ %{g:ipy_status}%)
endif


