from WindPy import w
w.start()

print("=== 信用利差测试 ===")
result1 = w.wsd("S0059760,S0059747", "close", "2026-03-16", "2026-03-17")
print(f"ErrorCode: {result1.ErrorCode}")
print(f"Times: {result1.Times}")
print(f"Data: {result1.Data}")

print("\n=== USD/CNY 测试 ===")
result2 = w.wsd("M0067855", "close", "2026-03-16", "2026-03-17")
print(f"ErrorCode: {result2.ErrorCode}")
print(f"Times: {result2.Times}")
print(f"Data: {result2.Data}")

print("\n=== 最近5天测试 ===")
result3 = w.wsd("S0059760,S0059747", "close", "2026-03-10", "2026-03-17")
print(f"ErrorCode: {result3.ErrorCode}")
print(f"Times: {result3.Times}")
print(f"Data: {result3.Data}")
