## 控制方式

- 客户端以tcp作为控制通道操作服务端，并通过命令告知服务端udp数据回传通道，如下所示
- 服务端默认控制端口号为：5025
- 客户端通过发送指令："*udp=xxx.xxx.xxx.xxx:yyyy\n"告知服务端
- 其中“*”为指令标识符，"udp"表示设置数据回传通道，回传地址为：xxx.xxx.xxx.xxx，端口号为：yyyy

## 参数指令

- 主要参数包含：频率（frequency,取值范围：70000000 ~ 6000000000） ，带宽（rf_bandwidth），采样率（sampling_frequency），增益控制模式（gain_control_mode，取值主要包含：manual和slow_attack）,手动增益（hardwaregain）
- 参数可以单独发送，也可以合并发送，指令格式为："#long:frequency:101700000;long:rf_bandwidth:2000000;long:samping_frequency:2500000;str:gain_control_mode:slow_attack\n"，由"参数类型(int或str)":"参数名":"参数值"组成
- 参数表

   中文名称|参数名称|参数类型|取值范围
   :--:|--|--|--
   __中心频率__|frequency|long|70MHz~6GHz
   __带宽__|rf_bandwidth|long|200kHz~56MHz
   __采样率__|samping_frequency|long|2500kHz~64MHz
   __增益控制__|gain_control_mode|str|[_slow_attack,fast_attack,manual_]
   __手动增益__|hardwaregain|int|-3dB~70dB
   __中心频率（发射）__|tx_frequency|long|70MHz~6GHz
   __发射使能__|tx_enabled|str|[_false,true_]


## 数据格式

- 数据包含：参数描述与iq数据
- 数据格式为：“#<8字节整型表示频率><8字节整型表示宽带><8字节整型表示采样率><4字节整型表示衰减><4字节整型表示后续iq总数><n字节数据表示iq>
- 其中"#"为数据标识符，每个合法的数据都带有该标识符，每个i或q数据皆为16位的带符号整型数据，即总共有n/4个iq数据，其中n为iq字节总数