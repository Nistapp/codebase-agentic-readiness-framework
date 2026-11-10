# How stock moves

Every count starts at zero when an item is first named, and each delivery that the caller records with the add method raises that count by the number of units that arrived in that delivery.

Each sale or withdrawal that the caller records with the take method lowers the count again, and the inventory checks first that the count would not fall below zero, so a count can never become negative.

When a count reaches the threshold, the item joins the low-stock list, and it leaves that list again as soon as a later delivery lifts the count back above the threshold.

The count lives in memory only.
A new inventory object starts empty.
Two inventory objects never share a count.
