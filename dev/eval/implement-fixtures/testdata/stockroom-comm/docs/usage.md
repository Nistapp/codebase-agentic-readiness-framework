# Usage

In order to add an item to the stock, the caller simply creates an inventory object and then calls the add method with the name of the item and the number of units that have arrived, and the inventory keeps the running count for that item in memory.

Taking items out of the stock is basically the same operation in reverse, because the take method looks up the item by its name, checks that enough units are left, and then lowers the count by the number of units that were asked for by the caller.

If the caller asks for more units than the inventory holds, the take method raises an error instead of letting the count fall below zero, which means that the caller has to catch that error and decide what to do about the missing units.

The low-stock list is easily produced by asking the inventory for every item whose count has fallen to or below the threshold that was given when the inventory object was first created by the caller at the start.

Counts are whole numbers.
Names are plain strings.
An unknown name is an error.
The inventory never writes to disk.
Nothing here needs a network.
Run the tests with `make test`.
