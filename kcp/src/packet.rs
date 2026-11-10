pub const KCP_HEADER_SIZE: usize = 24;

pub struct KCPSegment {
        pub header: KCPHeader,
        pub payload: Vec<u8>,
}

#[derive(Debug, PartialEq)]
pub struct KCPHeader {
        pub conversation: u32,
        pub command: u8,
        pub fragment: u8,
        pub window: u16,
        pub timestamp: u32,
        pub sequence: u32,
        pub next_expected: u32,
        pub length: u32, // payload 字节数
}

impl KCPSegment {
        pub fn encode(&self) -> Vec<u8> {
                todo!()
        }

        // 一个 UDP 数据报可能包含多个 KCP Segment，需要知道当前 Segment 消耗了多少字节，才能继续解析后面的数据。
        pub fn decode(bytes: &[u8]) -> Option<(Self, usize)> {
                todo!()
        }
}

impl KCPHeader {
        pub fn encode(&self) -> [u8; KCP_HEADER_SIZE] {
                let mut bytes = [0u8; KCP_HEADER_SIZE];

                // 传统网络字节序（Network Byte Order）使用大端序。例如：
                // - IPv4 Header 中的多字节字段
                // - TCP Header 中的多字节字段
                // - UDP Header 中的多字节字段
                // 但网络字节序并不强制所有应用层协议都使用大端序。
                //
                // KCP 作为封装在 UDP Payload 内的协议，可以自行规定字节序。
                // 原版 KCP 的 ikcp.c 使用低位字节优先的方式编码整数，因此采用小端序。
                // 重点是：通信双方必须遵循相同的字节序。

                bytes[0..4].copy_from_slice(&self.conversation.to_le_bytes());
                bytes[4] = self.command;
                bytes[5] = self.fragment;
                bytes[6..8].copy_from_slice(&self.window.to_le_bytes());
                bytes[8..12].copy_from_slice(&self.timestamp.to_le_bytes());
                bytes[12..16].copy_from_slice(&self.sequence.to_le_bytes());
                bytes[16..20].copy_from_slice(&self.next_expected.to_le_bytes());
                bytes[20..24].copy_from_slice(&self.length.to_le_bytes());

                bytes
        }

        pub fn decode(bytes: &[u8]) -> Option<Self> {
                if bytes.len() < KCP_HEADER_SIZE {
                        return None;
                }

                Some(Self {
                        conversation: u32::from_le_bytes(bytes[0..4].try_into().ok()?),
                        command: bytes[4],
                        fragment: bytes[5],
                        window: u16::from_le_bytes(bytes[6..8].try_into().ok()?),
                        timestamp: u32::from_le_bytes(bytes[8..12].try_into().ok()?),
                        sequence: u32::from_le_bytes(bytes[12..16].try_into().ok()?),
                        next_expected: u32::from_le_bytes(bytes[16..20].try_into().ok()?),
                        length: u32::from_le_bytes(bytes[20..24].try_into().ok()?),
                })
        }
}

#[cfg(test)]
mod tests {
        use super::*;

        #[test]
        fn encode_decode() {
                let header = KCPHeader {
                        conversation: 0x12345678,
                        command: 81,
                        fragment: 0,
                        window: 32,
                        timestamp: 1000,
                        sequence: 1,
                        next_expected: 0,
                        length: 5,
                };

                let bytes = header.encode();

                assert_eq!(bytes.len(), KCP_HEADER_SIZE);
                assert_eq!(&bytes[0..4], &[0x78, 0x56, 0x34, 0x12]);
                assert_eq!(KCPHeader::decode(&bytes), Some(header));
                assert_eq!(KCPHeader::decode(&bytes[..23]), None);
        }
}
