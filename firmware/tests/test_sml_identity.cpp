#include <cassert>
#include <cstring>

// The parser keeps the most recently decoded OBIS list in file-local storage.
// Include the implementation to exercise that storage without a UART device.
#include "../main/sml.cpp"

int main()
{
    const unsigned char manufacturer_entry[] = {
        6, SML_DATA_OCTET_STRING, 1, 0, 96, 50, 1, 1,
        0, SML_NEXT,
        0, SML_NEXT,
        0, SML_NEXT,
        0, SML_NEXT,
        3, SML_DATA_OCTET_STRING, 'E', 'M', 'H',
    };
    std::memcpy(listBuffer, manufacturer_entry, sizeof(manufacturer_entry));
    listPos = sizeof(manufacturer_entry);

    const unsigned char obis[] = {1, 0, 96, 50, 1, 1};
    assert(smlOBISCheck(obis));

    unsigned char value[8] = {};
    size_t length = 0;
    assert(smlOBISOctetString(value, sizeof(value), &length));
    assert(length == 3 && std::memcmp(value, "EMH", 3) == 0);
    assert(!smlOBISOctetString(value, 2, &length));

    // A truncated SML entry must never return a partial identifier.
    --listPos;
    assert(!smlOBISOctetString(value, sizeof(value), &length));

    const unsigned char nested_time_entry[] = {
        6, SML_DATA_OCTET_STRING, 1, 0, 96, 50, 1, 1,
        0, SML_NEXT,
        1, SML_LISTSTART, 1, SML_DATA_UNSIGNED_INT, 7,
        0, SML_NEXT,
        0, SML_NEXT,
        3, SML_DATA_OCTET_STRING, 'E', 'M', 'H',
    };
    std::memcpy(listBuffer, nested_time_entry, sizeof(nested_time_entry));
    listPos = sizeof(nested_time_entry);
    assert(smlOBISOctetString(value, sizeof(value), &length));
    assert(length == 3 && std::memcmp(value, "EMH", 3) == 0);

    listPos = 7;
    assert(!smlOBISCheck(obis));
}
