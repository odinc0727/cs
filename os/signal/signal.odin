package main

import "core:fmt"
import "core:sync"
import "core:sys/posix"

received_signal: i32 = 0

sigint_handler :: proc "c" (sig: posix.Signal) {
	sync.atomic_store(&received_signal, i32(sig))
}

main :: proc() {
	action: posix.sigaction_t
	action.sa_handler = sigint_handler
	_ = posix.sigemptyset(&action.sa_mask)

	if posix.sigaction(.SIGINT, &action, nil) != .OK {
		fmt.println("注册 SIGINT 失败")
		return
	}
	defer fmt.println("清理完成，程序退出")


	fmt.println("程序正在运行，按 Ctrl+C 发送 SIGINT")
	fmt.println("进程 ID:", posix.getpid())

	// 无限循环等待信号
	for sync.atomic_load(&received_signal) == 0 {
		fmt.println("等待信号中...")
		_ = posix.sleep(2)
	}

	fmt.printf("\n收到 SIGINT 信号，信号编号: %d\n", sync.atomic_load(&received_signal))
	fmt.println("程序即将退出...")
}
