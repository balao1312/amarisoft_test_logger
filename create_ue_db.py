import argparse

def create_ue_db(num=1, sim_algo="xor"):
    counter = 89
    output = ''
    for _ in range(num):
        template = f'''{{
    sim_algo: "{sim_algo}", /* USIM authentication algorithm: xor, milenage or tuak */
    imsi: "0010101234567{counter}", /* Anritsu Test USIM */
    amf: 0x9001, /* Authentication Management Field */
    sqn: "000000000000", /* Sequence Number */
    K: "00112233445566778899aabbccddeeff", /* Anritsu Test USIM */

    impi: "0010101234567{counter}@ims.mnc001.mcc001.3gppnetwork.org",
    impu: ["0010101234567{counter}", "tel:0600000000", "tel:600"],
    domain: "ims.mnc001.mcc001.3gppnetwork.org",
    multi_sim: true, /* Experimental */

    /* For standard SIP client */
    /*pwd:  "amarisoft",
    authent_type: "MD5",*/
}},\n'''
        output += template
        counter +=1

    with open('ue_db_created', 'w') as f:
        f.write(output)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--number', required=True,
                        type=int, help='number of UEs')
    parser.add_argument('-x', '--sim_algo', default='xor',
                        type=str, help='sim_algo')
    args = parser.parse_args()

    create_ue_db(args.number, args.sim_algo)
