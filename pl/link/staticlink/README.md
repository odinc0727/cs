```bash
cc -c add.c -o add.o          # 只编译，生成目标文件

ar rcs libadd.a add.o         # 把目标文件打包成静态库

cc main.c ./libadd.a -o main  # 编译并链接
# or:
cc main.c -L. -ladd -o main
```
